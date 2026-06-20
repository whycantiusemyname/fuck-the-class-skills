#!/usr/bin/env python3
"""Verify a pdf-to-markdown completion certificate."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
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


def verify_completion(completion_path: Path) -> None:
    completion_path = completion_path.expanduser().resolve()
    if not completion_path.is_file():
        raise CompletionError(f"completion.json does not exist: {completion_path}")
    payload = read_json(completion_path)
    if payload.get("schema_version") != 1 or payload.get("status") != "complete":
        raise CompletionError("completion schema/status is not complete")
    if payload.get("unresolved_count") != 0:
        raise CompletionError("completion has unresolved items")
    source_pdf = Path(payload.get("source_pdf", "")).expanduser().resolve()
    final_markdown = Path(payload.get("final_markdown", "")).expanduser().resolve()
    manifest = Path(payload.get("manifest", "")).expanduser().resolve()
    if not source_pdf.is_file() or sha256_file(source_pdf) != payload.get("source_pdf_sha256"):
        raise CompletionError("source_pdf hash mismatch")
    if not final_markdown.is_file() or sha256_file(final_markdown) != payload.get("final_markdown_sha256"):
        raise CompletionError("final_markdown hash mismatch")
    if not manifest.is_file() or sha256_file(manifest) != payload.get("manifest_sha256"):
        raise CompletionError("manifest hash mismatch")
    manifest_payload = read_json(manifest)
    unresolved_chunks = [record for record in manifest_payload.get("chunks", []) if record.get("status") != "done"]
    if unresolved_chunks:
        raise CompletionError(f"manifest still has unresolved chunks: {len(unresolved_chunks)}")
    segment_manifest_raw = payload.get("segment_manifest")
    if segment_manifest_raw:
        segment_manifest = Path(segment_manifest_raw).expanduser().resolve()
        if not segment_manifest.is_file() or sha256_file(segment_manifest) != payload.get("segment_manifest_sha256"):
            raise CompletionError("segment manifest hash mismatch")
        segment_payload = read_json(segment_manifest)
        missing = [segment.get("repaired_path") for segment in segment_payload.get("segments", []) if not Path(segment.get("repaired_path", "")).is_file()]
        if missing and not payload.get("llm_readthrough", {}).get("allow_unrepaired_segments"):
            raise CompletionError("missing repaired LLM readthrough segments: " + ", ".join(map(str, missing[:5])))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, help="Workspace containing completion.json")
    parser.add_argument("--completion", type=Path, help="Explicit completion.json path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if bool(args.work_dir) == bool(args.completion):
        print("provide exactly one of --work-dir or --completion", file=sys.stderr)
        return 2
    completion = args.completion or (args.work_dir / "completion.json")
    try:
        verify_completion(completion)
    except CompletionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"completion verified: {completion}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
