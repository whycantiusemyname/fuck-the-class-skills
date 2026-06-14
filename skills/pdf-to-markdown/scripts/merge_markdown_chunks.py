from __future__ import annotations

import argparse
import json
from pathlib import Path

from mineru_common import read_json


def merge_chunks(manifest_path: Path, output_md: Path, merge_report_path: Path) -> tuple[Path, Path]:
    manifest = read_json(manifest_path)
    successful = sorted(
        [record for record in manifest["chunks"] if record.get("normalized_markdown")],
        key=lambda item: item["start_page"],
    )
    if not successful:
        raise RuntimeError("No normalized Markdown chunks were found to merge.")

    merged_parts: list[str] = []
    per_chunk_metadata_files: list[str] = []

    for record in successful:
        chunk_text = Path(record["normalized_markdown"]).read_text(encoding="utf-8").strip()
        merged_parts.append(chunk_text)
        if record.get("metadata_path"):
            per_chunk_metadata_files.append(record["metadata_path"])

    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n\n".join(part for part in merged_parts if part) + "\n", encoding="utf-8")

    report_payload = {
        "merged_output": str(output_md),
        "per_chunk_metadata_files": per_chunk_metadata_files,
        "mode": "pass-through",
        "llm_readthrough_required": True,
    }
    merge_report_path.parent.mkdir(parents=True, exist_ok=True)
    merge_report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_md, merge_report_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge successful normalized Markdown chunks into one draft.")
    parser.add_argument("manifest_path", help="Path to the manifest JSON.")
    parser.add_argument("--output-md", required=True, help="Destination merged Markdown path.")
    parser.add_argument("--merge-report-path", required=True, help="Destination merged metadata report path.")
    args = parser.parse_args()

    merge_chunks(
        Path(args.manifest_path).expanduser().resolve(),
        Path(args.output_md).expanduser().resolve(),
        Path(args.merge_report_path).expanduser().resolve(),
    )
    print(f"Merged Markdown written to {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
