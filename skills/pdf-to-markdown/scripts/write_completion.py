#!/usr/bin/env python3
"""Write a completion certificate for a finished pdf-to-markdown workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CompletionError(Exception):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompletionError(f"Cannot read JSON {path}: {exc}") from exc


def unresolved_from_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    unresolved: list[dict[str, Any]] = []
    for record in manifest.get("chunks", []):
        status = record.get("status")
        if status != "done":
            unresolved.append(
                {
                    "chunk_id": record.get("chunk_id"),
                    "start_page": record.get("start_page"),
                    "end_page": record.get("end_page"),
                    "status": status,
                    "error_code": record.get("error_code"),
                    "error_message": record.get("error_message"),
                }
            )
    return unresolved


def segment_status(segment_manifest: Path) -> tuple[int, int, list[str]]:
    if not segment_manifest.exists():
        return 0, 0, [f"missing segment manifest: {segment_manifest}"]
    payload = read_json(segment_manifest)
    total = 0
    repaired = 0
    missing: list[str] = []
    for segment in payload.get("segments", []):
        total += 1
        path = Path(segment.get("repaired_path", ""))
        if path.exists() and path.is_file():
            repaired += 1
        else:
            missing.append(str(path))
    return total, repaired, missing


def write_completion(source_pdf: Path, final_markdown: Path, work_dir: Path, *, allow_unrepaired_segments: bool = False) -> Path:
    source_pdf = source_pdf.expanduser().resolve()
    final_markdown = final_markdown.expanduser().resolve()
    work_dir = work_dir.expanduser().resolve()
    if not source_pdf.is_file():
        raise CompletionError(f"source PDF does not exist: {source_pdf}")
    if not final_markdown.is_file():
        raise CompletionError(f"final Markdown does not exist: {final_markdown}")
    manifest_path = work_dir / "manifest.json"
    if not manifest_path.is_file():
        raise CompletionError(f"manifest.json does not exist: {manifest_path}")
    manifest = read_json(manifest_path)
    recorded_source = Path(manifest.get("source_pdf", "")).expanduser().resolve()
    if recorded_source != source_pdf:
        raise CompletionError("manifest source_pdf does not match requested source PDF")
    unresolved = unresolved_from_manifest(manifest)

    segment_manifest = work_dir / "reports" / "llm_readthrough_segments" / "manifest.json"
    segment_count, repaired_count, missing_repaired = segment_status(segment_manifest)
    if missing_repaired and not allow_unrepaired_segments:
        unresolved.extend(
            {
                "kind": "llm_readthrough_segment",
                "status": "missing_repaired_segment",
                "path": path,
            }
            for path in missing_repaired
        )

    completion = {
        "schema_version": 1,
        "status": "complete" if not unresolved else "blocked",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_pdf": str(source_pdf),
        "source_pdf_sha256": sha256_file(source_pdf),
        "final_markdown": str(final_markdown),
        "final_markdown_sha256": sha256_file(final_markdown),
        "work_dir": str(work_dir),
        "manifest": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "segment_manifest": str(segment_manifest) if segment_manifest.exists() else None,
        "segment_manifest_sha256": sha256_file(segment_manifest) if segment_manifest.exists() else None,
        "llm_readthrough": {
            "segment_count": segment_count,
            "repaired_count": repaired_count,
            "allow_unrepaired_segments": allow_unrepaired_segments,
        },
        "unresolved_count": len(unresolved),
        "unresolved": unresolved,
    }
    target = work_dir / "completion.json"
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(completion, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(target)
    if unresolved:
        raise CompletionError(f"completion blocked with {len(unresolved)} unresolved item(s); see {target}")
    return target


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-pdf", required=True, type=Path)
    parser.add_argument("--final-markdown", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument(
        "--allow-unrepaired-segments",
        action="store_true",
        help="Allow completion before the segmented LLM readthrough repaired files exist. Use only for explicit draft-mode workflows.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        target = write_completion(
            args.source_pdf,
            args.final_markdown,
            args.work_dir,
            allow_unrepaired_segments=args.allow_unrepaired_segments,
        )
    except CompletionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"completion written: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
