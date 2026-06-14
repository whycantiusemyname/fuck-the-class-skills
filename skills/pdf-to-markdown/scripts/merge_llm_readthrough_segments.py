from __future__ import annotations

import argparse
import json
from pathlib import Path


def merge_repaired_segments(manifest_path: Path, output_md: Path, *, allow_source_fallback: bool = False) -> Path:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    parts: list[str] = []
    missing: list[str] = []

    for segment in manifest.get("segments", []):
        repaired_path = Path(segment["repaired_path"])
        source_path = Path(segment["source_path"])
        if repaired_path.exists():
            parts.append(repaired_path.read_text(encoding="utf-8"))
            continue
        if allow_source_fallback and source_path.exists():
            parts.append(source_path.read_text(encoding="utf-8"))
            continue
        missing.append(str(repaired_path))

    if missing:
        raise FileNotFoundError("Missing repaired segments: " + ", ".join(missing))

    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("".join(parts), encoding="utf-8")
    return output_md


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge repaired LLM readthrough segments back into one Markdown file.")
    parser.add_argument("manifest_path", help="Path to the segment manifest JSON.")
    parser.add_argument("--output-md", required=True, help="Destination merged Markdown path.")
    parser.add_argument(
        "--allow-source-fallback",
        action="store_true",
        help="Allow unrepaired segments to fall back to the original source segment content.",
    )
    args = parser.parse_args()

    merge_repaired_segments(
        Path(args.manifest_path).expanduser().resolve(),
        Path(args.output_md).expanduser().resolve(),
        allow_source_fallback=args.allow_source_fallback,
    )
    print(f"Merged repaired segments into {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
