from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader, PdfWriter


def parse_range(spec: str, total_pages: int) -> tuple[int, int]:
    if "-" not in spec:
        raise ValueError(f"Invalid range '{spec}'. Expected START-END.")
    start_text, end_text = spec.split("-", 1)
    start = int(start_text)
    end = int(end_text)
    if start < 1 or end < 1 or start > end:
        raise ValueError(f"Invalid range '{spec}'.")
    if end > total_pages:
        raise ValueError(f"Range '{spec}' exceeds total pages ({total_pages}).")
    return start, end


def iter_chunk_ranges(total_pages: int, chunk_size: int) -> Iterable[tuple[int, int]]:
    start = 1
    while start <= total_pages:
        end = min(start + chunk_size - 1, total_pages)
        yield start, end
        start = end + 1


def write_chunk(
    reader: PdfReader,
    start: int,
    end: int,
    output_dir: Path,
    stem: str,
) -> Path:
    writer = PdfWriter()
    for page_index in range(start - 1, end):
        writer.add_page(reader.pages[page_index])

    out_path = output_dir / f"{stem}_p{start:03d}-{end:03d}.pdf"
    with out_path.open("wb") as handle:
        writer.write(handle)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Split a PDF into smaller PDFs by fixed chunk size or explicit page ranges."
    )
    parser.add_argument("input_pdf", help="Path to the input PDF.")
    parser.add_argument(
        "--output-dir",
        help="Directory for split PDFs. Defaults to a sibling '<stem>_chunks' folder.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--chunk-size",
        type=int,
        help="Split into consecutive chunks of this many pages.",
    )
    group.add_argument(
        "--ranges",
        nargs="+",
        help="Explicit 1-based page ranges, e.g. 1-12 13-27 28-40.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the chunk plan without writing files.",
    )
    args = parser.parse_args()

    input_pdf = Path(args.input_pdf).expanduser().resolve()
    if not input_pdf.exists():
        raise FileNotFoundError(f"Input PDF not found: {input_pdf}")

    reader = PdfReader(str(input_pdf))
    total_pages = len(reader.pages)
    if total_pages == 0:
        raise ValueError("The input PDF has no pages.")

    if args.chunk_size is not None:
        if args.chunk_size < 1:
            raise ValueError("--chunk-size must be at least 1.")
        ranges = list(iter_chunk_ranges(total_pages, args.chunk_size))
    else:
        ranges = [parse_range(spec, total_pages) for spec in args.ranges]

    if args.output_dir:
        output_dir = Path(args.output_dir).expanduser().resolve()
    else:
        output_dir = input_pdf.with_name(f"{input_pdf.stem}_chunks")

    print(f"Input: {input_pdf}")
    print(f"Total pages: {total_pages}")
    print(f"Output dir: {output_dir}")
    for start, end in ranges:
        print(f"Chunk: {start}-{end}")

    if args.dry_run:
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    for start, end in ranges:
        out_path = write_chunk(reader, start, end, output_dir, input_pdf.stem)
        print(f"Wrote: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
