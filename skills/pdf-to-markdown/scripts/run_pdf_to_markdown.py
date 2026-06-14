from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from merge_markdown_chunks import merge_chunks
from mineru_common import (
    PARSE_RETRY_LIMIT,
    SAFE_PAGE_LIMIT,
    SAFE_SIZE_LIMIT_BYTES,
    append_history,
    classify_error,
    ensure_dir,
    make_data_id,
    read_json,
    write_json,
)
from mineru_fetch_results import fetch_results
from mineru_poll_batch import poll_manifest
from mineru_submit_batch import submit_manifest
from normalize_obsidian_output import normalize_chunk
from pdf_workflow import (
    create_workflow_state,
    make_run_id,
    reset_postprocessing_artifacts,
    sha256_file,
)
from prepare_llm_readthrough_segments import prepare_segments
from prepare_pdf_chunks import prepare_chunks, split_range
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader


def find_full_markdown(extract_dir: Path) -> Path:
    candidates = sorted(path for path in extract_dir.rglob("full.md") if path.is_file())
    if not candidates:
        raise FileNotFoundError(f"Could not find full.md under {extract_dir}")
    return candidates[0]


MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
OBSIDIAN_EMBED_RE = re.compile(r"!\[\[([^\]]+)\]\]")


def choose_embed_width(image_path: Path, max_width: int | None) -> int | None:
    if max_width is None:
        return None
    try:
        with Image.open(image_path) as image:
            actual_width = int(image.size[0])
    except (UnidentifiedImageError, OSError, ValueError):
        return max_width
    if actual_width <= max_width:
        return None
    return max_width


def apply_obsidian_image_width(
    text: str,
    image_width: int | None,
    image_resolver: callable | None = None,
) -> str:
    if image_width is None:
        return text

    def replace_embed(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        path_part = inner.split("|", 1)[0].strip()
        chosen_width = image_width
        if image_resolver is not None:
            chosen_width = choose_embed_width(image_resolver(path_part), image_width)
        if chosen_width is None:
            return f"![[{path_part}]]"
        return f"![[{path_part}|{chosen_width}]]"

    text = OBSIDIAN_EMBED_RE.sub(replace_embed, text)
    if OBSIDIAN_EMBED_RE.search(text):
        return text

    def replace_markdown(match: re.Match[str]) -> str:
        original = match.group(2).strip()
        chosen_width = image_width
        if image_resolver is not None:
            chosen_width = choose_embed_width(image_resolver(original), image_width)
        if chosen_width is None:
            return f"![[{original}]]"
        return f"![[{original}|{chosen_width}]]"

    return MARKDOWN_IMAGE_RE.sub(replace_markdown, text)


def reset_for_retry(record: dict) -> None:
    record["parse_attempts"] += 1
    record["status"] = "retry-pending"
    record["batch_id"] = None
    record["upload_url"] = None
    record["result_zip_url"] = None
    record["result_zip_path"] = None
    record["result_dir"] = None
    record["normalized_markdown"] = None
    record["metadata_path"] = None
    record["error_code"] = None
    record["data_id"] = make_data_id(
        Path(record["source_pdf"]).stem,
        record["start_page"],
        record["end_page"],
        record["parse_attempts"],
    )
    append_history(record, "Prepared the chunk for a fresh parse retry.")


def resplit_failed_chunk(manifest: dict, record: dict, chunks_dir: Path) -> None:
    source_pdf = Path(manifest["source_pdf"])
    reader = PdfReader(str(source_pdf))
    new_records: list[dict] = []
    split_range(
        reader,
        source_pdf,
        chunks_dir,
        record["start_page"],
        record["end_page"],
        manifest["page_limit"],
        manifest["size_limit_bytes"],
        int(record.get("split_depth", 0)) + 1,
        new_records,
    )
    for new_record in new_records:
        append_history(new_record, f"Created by re-splitting failed range {record['chunk_id']}.")
    manifest["chunks"] = [
        item for item in manifest["chunks"] if item["chunk_id"] != record["chunk_id"]
    ] + new_records


def process_failures(manifest_path: Path) -> dict:
    manifest = read_json(manifest_path)
    chunks_dir = Path(manifest["chunks_dir"])
    changed = False
    for record in list(manifest["chunks"]):
        if record.get("status") != "failed":
            continue
        category = classify_error(record.get("error_code"), record.get("error_message"))
        if category == "resplit" and record["page_count"] > 1:
            append_history(record, "Marked for re-splitting after oversize or page-limit failure.")
            resplit_failed_chunk(manifest, record, chunks_dir)
            changed = True
            continue
        if category in {"retry", "unknown"} and record.get("parse_attempts", 0) < PARSE_RETRY_LIMIT:
            reset_for_retry(record)
            changed = True
            continue
        record["status"] = "final-failed"
        append_history(record, "Marked as final failure after retry handling was exhausted.")
    if changed:
        manifest["chunks"] = sorted(manifest["chunks"], key=lambda item: item["start_page"])
    write_json(manifest_path, manifest)
    return manifest


def normalize_successes(
    manifest_path: Path,
    normalized_dir: Path,
    assets_root: Path,
    note_stem: str,
    image_width: int | None = None,
) -> dict:
    manifest = read_json(manifest_path)
    for record in manifest["chunks"]:
        if record.get("status") != "done" or not record.get("result_dir"):
            continue
        output_md = normalized_dir / f"{record['chunk_id']}.md"
        metadata_path = normalized_dir / f"{record['chunk_id']}.metadata.json"
        normalize_chunk(
            Path(record["result_dir"]),
            output_md,
            metadata_path,
            assets_root,
            note_stem=note_stem,
            start_page=record["start_page"],
            end_page=record["end_page"],
            image_width=image_width,
        )
        record["normalized_markdown"] = str(output_md)
        record["metadata_path"] = str(metadata_path)
        append_history(record, f"Normalized Markdown written to {output_md}.")
    write_json(manifest_path, manifest)
    return manifest


def export_single_chunk_passthrough(
    manifest_path: Path,
    output_md: Path,
    reports_dir: Path,
    image_width: int | None = None,
) -> dict:
    manifest = read_json(manifest_path)
    successful = [record for record in manifest["chunks"] if record.get("status") == "done" and record.get("result_dir")]
    if len(successful) != 1 or len(manifest["chunks"]) != 1:
        raise RuntimeError("Single-chunk passthrough requires exactly one successful chunk.")

    record = successful[0]
    extract_dir = Path(record["result_dir"])
    full_md = find_full_markdown(extract_dir)
    output_md.parent.mkdir(parents=True, exist_ok=True)

    if full_md.resolve() != output_md.resolve():
        shutil.copy2(full_md, output_md)

    def resolve_passthrough_image(relative_path: str) -> Path:
        return output_md.parent / relative_path

    images_dir = full_md.parent / "images"
    copied_images = False
    if images_dir.exists() and images_dir.is_dir():
        shutil.copytree(images_dir, output_md.parent / "images", dirs_exist_ok=True)
        copied_images = True

    if image_width is not None:
        text = output_md.read_text(encoding="utf-8")
        text = apply_obsidian_image_width(text, image_width, image_resolver=resolve_passthrough_image)
        output_md.write_text(text, encoding="utf-8")

    record["exported_markdown"] = str(output_md)
    append_history(record, f"Exported MinerU full.md directly to {output_md}.")
    report_payload = {
        "mode": "single-chunk-passthrough",
        "source_full_md": str(full_md),
        "exported_markdown": str(output_md),
        "images_copied": copied_images,
        "images_destination": str(output_md.parent / "images") if copied_images else None,
        "image_width": image_width,
        "content_transform": "image-width-only" if image_width is not None else "none",
    }
    write_json(reports_dir / "passthrough_report.json", report_payload)
    write_json(manifest_path, manifest)
    return manifest


def write_failure_report(manifest: dict, report_path: Path) -> None:
    failures = [record for record in manifest["chunks"] if record.get("status") == "final-failed"]
    successful = [
        record
        for record in manifest["chunks"]
        if record.get("normalized_markdown") or record.get("exported_markdown") or record.get("status") == "done"
    ]
    total = len(manifest["chunks"]) or 1
    failure_ratio = len(failures) / total
    payload = {
        "source_pdf": manifest["source_pdf"],
        "failed_ranges": [
            {
                "chunk_id": record["chunk_id"],
                "start_page": record["start_page"],
                "end_page": record["end_page"],
                "error_code": record.get("error_code"),
                "error_message": record.get("error_message"),
                "history": record.get("history", []),
            }
            for record in failures
        ],
        "successful_ranges": [
            {
                "chunk_id": record["chunk_id"],
                "start_page": record["start_page"],
                "end_page": record["end_page"],
            }
            for record in successful
        ],
        "failure_ratio": failure_ratio,
        "recommended_action": "Stop this workflow and report the unresolved ranges to the user.",
        "fallback_started": False,
    }
    write_json(report_path, payload)


def write_llm_readthrough_prompt(
    manifest: dict,
    draft_md: Path,
    requested_output: Path,
    reports_dir: Path,
    segment_manifest_path: Path,
) -> None:
    successful_ranges = [
        f"{record['start_page']}-{record['end_page']}"
        for record in manifest["chunks"]
        if record.get("status") == "done"
    ]
    failed_ranges = [
        f"{record['start_page']}-{record['end_page']}"
        for record in manifest["chunks"]
        if record.get("status") == "final-failed"
    ]

    prompt_text = f"""Read the entire Markdown file and repair it for Obsidian readability.

Goals:
- Process the document segment by segment until all segments are repaired.
- Fix malformed math so Obsidian MathJax can render it.
- Clean up obvious formatting damage caused by PDF parsing.
- Preserve the source meaning, section order, tables, images, and links.

Rules:
- Work from the generated segment files in order.
- Preserve image paths exactly as they already appear in each segment.
- Preserve table structure unless a table row is completely invalid; prefer the smallest possible fix.
- Use `$...$` for inline math and `$$ ... $$` for display math.
- Fix unsupported or broken LaTeX wrappers when the intended math is clear.
- Keep wording changes minimal; repair formatting and math before prose.
- Do not invent missing content.

Files:
- MinerU draft: {draft_md}
- Requested final Markdown: {requested_output}

Segment package:
- Segment manifest: {segment_manifest_path}
- Source segments: {segment_manifest_path.parent / "source"}
- Per-segment prompts: {segment_manifest_path.parent / "prompts"}
- Repaired segment outputs: {segment_manifest_path.parent / "repaired"}

Context:
- MinerU work dir: {reports_dir.parent}
- Successful page ranges: {", ".join(successful_ranges) or "none"}
- Failed page ranges: {", ".join(failed_ranges) or "none"}

Return:
- Repair each segment and save the result to the matching path under the repaired directory.
- After all segments are repaired, run validate_text_repairs.py.
- Do not write the requested final Markdown directly. It is created only after visual source verification.
"""
    prompt_path = reports_dir / "llm_readthrough_prompt.txt"
    prompt_path.write_text(prompt_text, encoding="utf-8")


def run_pipeline(input_pdf: Path, output_md: Path, work_dir: Path, image_width: int | None = None) -> int:
    note_stem = output_md.stem
    draft_md = work_dir / "draft.md"
    if output_md.resolve() == draft_md.resolve():
        raise ValueError("The requested final Markdown cannot be the reserved work_dir/draft.md path.")
    source_pdf_sha256 = sha256_file(input_pdf)
    run_id = make_run_id(input_pdf, source_pdf_sha256)
    reset_postprocessing_artifacts(work_dir)
    manifest_path = work_dir / "manifest.json"
    chunks_dir = ensure_dir(work_dir / "chunks")
    results_dir = ensure_dir(work_dir / "results")
    normalized_dir = ensure_dir(work_dir / "normalized")
    reports_dir = ensure_dir(work_dir / "reports")
    assets_root = work_dir / "assets"

    prepare_chunks(
        input_pdf,
        chunks_dir,
        manifest_path,
        page_limit=SAFE_PAGE_LIMIT,
        size_limit_bytes=SAFE_SIZE_LIMIT_BYTES,
    )

    while True:
        manifest = read_json(manifest_path)
        pending = [record for record in manifest["chunks"] if record["status"] in {"prepared", "retry-pending"}]
        if pending:
            submit_manifest(
                manifest_path,
                model_version="vlm",
                language="ch",
                enable_formula=True,
                enable_table=True,
                is_ocr=False,
            )
            poll_manifest(manifest_path)
            manifest = process_failures(manifest_path)
            if any(record["status"] in {"prepared", "retry-pending"} for record in manifest["chunks"]):
                continue
        break

    manifest = read_json(manifest_path)
    fetch_results(manifest_path, results_dir)
    manifest = read_json(manifest_path)
    successful = [record for record in manifest["chunks"] if record.get("status") == "done" and record.get("result_dir")]
    if len(manifest["chunks"]) == 1 and len(successful) == 1:
        export_single_chunk_passthrough(manifest_path, draft_md, reports_dir, image_width=image_width)
    else:
        normalize_successes(
            manifest_path,
            normalized_dir,
            assets_root,
            note_stem,
            image_width=image_width,
        )
        merge_chunks(
            manifest_path,
            draft_md,
            reports_dir / "merge_report.json",
        )
    manifest = read_json(manifest_path)
    segment_manifest = prepare_segments(
        draft_md,
        reports_dir / "llm_readthrough_segments",
        run_id=run_id,
    )
    segment_manifest_path = reports_dir / "llm_readthrough_segments" / "manifest.json"
    write_llm_readthrough_prompt(
        manifest,
        draft_md,
        output_md,
        reports_dir,
        segment_manifest_path,
    )
    failures = [record for record in manifest["chunks"] if record["status"] == "final-failed"]
    if failures:
        write_failure_report(manifest, reports_dir / "fallback_report.json")
        create_workflow_state(
            work_dir,
            run_id=run_id,
            source_pdf=input_pdf,
            requested_output=output_md,
            draft_md=draft_md,
            segment_manifest=segment_manifest_path,
            page_count=sum(int(record["page_count"]) for record in manifest["chunks"]),
            status="blocked",
            source_pdf_sha256=source_pdf_sha256,
            blockers=[
                f"MinerU final failure for pages {record['start_page']}-{record['end_page']}: "
                f"{record.get('error_message') or record.get('error_code') or 'unknown error'}"
                for record in failures
            ],
        )
        return 2
    create_workflow_state(
        work_dir,
        run_id=run_id,
        source_pdf=input_pdf,
        requested_output=output_md,
        draft_md=draft_md,
        segment_manifest=segment_manifest_path,
        page_count=len(PdfReader(str(input_pdf)).pages),
        source_pdf_sha256=source_pdf_sha256,
    )
    print(
        f"MinerU draft and {segment_manifest['segment_count']} repair segments are ready. "
        "The workflow is incomplete until text repair, visual verification, and finalization pass."
    )
    return 3


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the MinerU-first PDF-to-Markdown workflow.")
    parser.add_argument("input_pdf", help="Path to the local PDF file.")
    parser.add_argument("output_md", help="Path to the merged Markdown draft.")
    parser.add_argument(
        "--work-dir",
        required=True,
        help="Directory for manifest, chunks, downloads, normalized chunks, and reports.",
    )
    parser.add_argument("--image-width", type=int, help="Optional Obsidian image width to append as |WIDTH.")
    args = parser.parse_args()

    return run_pipeline(
        Path(args.input_pdf).expanduser().resolve(),
        Path(args.output_md).expanduser().resolve(),
        Path(args.work_dir).expanduser().resolve(),
        image_width=args.image_width,
    )


if __name__ == "__main__":
    raise SystemExit(main())
