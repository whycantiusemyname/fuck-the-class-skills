from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter

from mineru_common import (
    SAFE_PAGE_LIMIT,
    SAFE_SIZE_LIMIT_BYTES,
    append_history,
    make_data_id,
    write_json,
)


def write_range(reader: PdfReader, start_page: int, end_page: int, destination: Path) -> int:
    writer = PdfWriter()
    for page_index in range(start_page - 1, end_page):
        writer.add_page(reader.pages[page_index])
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        writer.write(handle)
    return destination.stat().st_size


def chunk_path(output_dir: Path, stem: str, start_page: int, end_page: int) -> Path:
    return output_dir / f"{stem}_p{start_page:04d}-{end_page:04d}.pdf"


def split_range(
    reader: PdfReader,
    source_pdf: Path,
    output_dir: Path,
    start_page: int,
    end_page: int,
    page_limit: int,
    size_limit_bytes: int,
    split_depth: int,
    chunk_records: list[dict[str, Any]],
) -> None:
    page_count = end_page - start_page + 1
    if page_count > page_limit:
        cursor = start_page
        while cursor <= end_page:
            child_end = min(cursor + page_limit - 1, end_page)
            split_range(
                reader,
                source_pdf,
                output_dir,
                cursor,
                child_end,
                page_limit,
                size_limit_bytes,
                split_depth + 1,
                chunk_records,
            )
            cursor = child_end + 1
        return

    destination = chunk_path(output_dir, source_pdf.stem, start_page, end_page)
    size_bytes = write_range(reader, start_page, end_page, destination)
    if size_bytes <= size_limit_bytes:
        record = {
            "chunk_id": f"p{start_page:04d}-{end_page:04d}",
            "source_pdf": str(source_pdf),
            "file_path": str(destination),
            "start_page": start_page,
            "end_page": end_page,
            "page_count": page_count,
            "size_bytes": size_bytes,
            "split_depth": split_depth,
            "data_id": make_data_id(source_pdf.stem, start_page, end_page),
            "submit_attempts": 0,
            "upload_attempts": 0,
            "parse_attempts": 0,
            "status": "prepared",
            "batch_id": None,
            "upload_url": None,
            "result_zip_url": None,
            "result_zip_path": None,
            "result_dir": None,
            "normalized_markdown": None,
            "metadata_path": None,
            "error_code": None,
            "error_message": None,
            "history": [],
        }
        append_history(record, f"Prepared chunk {destination.name} ({page_count} pages, {size_bytes} bytes).")
        chunk_records.append(record)
        return

    destination.unlink(missing_ok=True)
    if page_count == 1:
        raise RuntimeError(
            "A single-page chunk still exceeds the safe size limit. "
            f"Page {start_page} alone is larger than {size_limit_bytes} bytes."
        )

    midpoint = start_page + (page_count // 2) - 1
    split_range(
        reader,
        source_pdf,
        output_dir,
        start_page,
        midpoint,
        page_limit,
        size_limit_bytes,
        split_depth + 1,
        chunk_records,
    )
    split_range(
        reader,
        source_pdf,
        output_dir,
        midpoint + 1,
        end_page,
        page_limit,
        size_limit_bytes,
        split_depth + 1,
        chunk_records,
    )


def prepare_chunks(
    input_pdf: Path,
    output_dir: Path,
    manifest_path: Path,
    *,
    page_limit: int = SAFE_PAGE_LIMIT,
    size_limit_bytes: int = SAFE_SIZE_LIMIT_BYTES,
) -> dict[str, Any]:
    reader = PdfReader(str(input_pdf))
    total_pages = len(reader.pages)
    if total_pages == 0:
        raise ValueError("The input PDF has no pages.")

    chunk_records: list[dict[str, Any]] = []
    split_range(
        reader,
        input_pdf,
        output_dir,
        1,
        total_pages,
        page_limit,
        size_limit_bytes,
        0,
        chunk_records,
    )
    manifest = {
        "source_pdf": str(input_pdf),
        "source_size_bytes": input_pdf.stat().st_size,
        "total_pages": total_pages,
        "page_limit": page_limit,
        "size_limit_bytes": size_limit_bytes,
        "chunks_dir": str(output_dir),
        "chunks": sorted(chunk_records, key=lambda item: item["start_page"]),
    }
    write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare safe PDF chunks for MinerU upload and write a manifest."
    )
    parser.add_argument("input_pdf", help="Path to the source PDF.")
    parser.add_argument("--output-dir", required=True, help="Directory for generated chunks.")
    parser.add_argument("--manifest-path", required=True, help="Path to the output manifest JSON.")
    parser.add_argument(
        "--page-limit",
        type=int,
        default=SAFE_PAGE_LIMIT,
        help=f"Safe page limit per chunk. Default: {SAFE_PAGE_LIMIT}.",
    )
    parser.add_argument(
        "--size-limit-mb",
        type=int,
        default=SAFE_SIZE_LIMIT_BYTES // (1024 * 1024),
        help=f"Safe size limit per chunk in MB. Default: {SAFE_SIZE_LIMIT_BYTES // (1024 * 1024)}.",
    )
    args = parser.parse_args()

    manifest = prepare_chunks(
        Path(args.input_pdf).expanduser().resolve(),
        Path(args.output_dir).expanduser().resolve(),
        Path(args.manifest_path).expanduser().resolve(),
        page_limit=args.page_limit,
        size_limit_bytes=args.size_limit_mb * 1024 * 1024,
    )
    print(f"Wrote manifest: {args.manifest_path}")
    print(f"Prepared {len(manifest['chunks'])} chunks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
