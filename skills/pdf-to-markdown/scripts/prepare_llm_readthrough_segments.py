from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def choose_split_index(lines: list[str], max_chars: int) -> int:
    total = 0
    split_index = len(lines)
    fallback_index = len(lines)
    for index, line in enumerate(lines, start=1):
        total += len(line)
        if total >= max_chars:
            fallback_index = index
            break

    if fallback_index == len(lines):
        return fallback_index

    running = 0
    best_blank_index = 0
    for index, line in enumerate(lines[:fallback_index], start=1):
        running += len(line)
        if running < max_chars * 0.5:
            continue
        if not line.strip():
            best_blank_index = index

    return best_blank_index or fallback_index


def split_markdown(text: str, max_chars: int) -> list[dict[str, object]]:
    lines = text.splitlines(keepends=True)
    if not lines:
        return [{"text": "", "start_line": 1, "end_line": 1}]

    segments: list[dict[str, object]] = []
    current_line = 1
    remaining = lines[:]
    while remaining:
        split_index = choose_split_index(remaining, max_chars)
        segment_lines = remaining[:split_index]
        segment_text = "".join(segment_lines)
        end_line = current_line + len(segment_lines) - 1
        segments.append(
            {
                "text": segment_text,
                "start_line": current_line,
                "end_line": end_line,
            }
        )
        remaining = remaining[split_index:]
        current_line = end_line + 1
    return segments


def build_segment_prompt(source_path: Path, segment_path: Path, segment_number: int, total_segments: int) -> str:
    return f"""Repair this Markdown segment for Obsidian readability.

Segment:
- Source markdown: {source_path}
- Segment file: {segment_path}
- Segment number: {segment_number} / {total_segments}

Goals:
- Read this entire segment before editing.
- Fix math formatting so Obsidian MathJax can render it.
- Fix obvious PDF-parsing formatting damage.
- Preserve meaning, order, image paths, and table structure.

Rules:
- Return repaired Markdown for this segment only.
- Do not add commentary.
- Use `$...$` for inline math.
- Use `$$ ... $$` for display math.
- Preserve image paths exactly.
- Preserve table structure unless a tiny local fix is required.
- Keep wording changes minimal; repair formatting and math before prose.
- Do not invent missing content.
"""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_segments(
    markdown_path: Path,
    output_dir: Path,
    max_chars: int = 12000,
    run_id: str | None = None,
) -> dict[str, object]:
    text = markdown_path.read_text(encoding="utf-8")
    segments = split_markdown(text, max_chars=max_chars)

    if output_dir.exists():
        shutil.rmtree(output_dir)

    source_dir = output_dir / "source"
    prompt_dir = output_dir / "prompts"
    repaired_dir = output_dir / "repaired"
    source_dir.mkdir(parents=True, exist_ok=True)
    prompt_dir.mkdir(parents=True, exist_ok=True)
    repaired_dir.mkdir(parents=True, exist_ok=True)

    manifest_segments: list[dict[str, object]] = []
    total_segments = len(segments)
    for index, segment in enumerate(segments, start=1):
        source_path = source_dir / f"segment-{index:03d}.md"
        prompt_path = prompt_dir / f"segment-{index:03d}.txt"
        repaired_path = repaired_dir / f"segment-{index:03d}.md"
        source_path.write_text(str(segment["text"]), encoding="utf-8")
        prompt_path.write_text(
            build_segment_prompt(markdown_path, source_path, index, total_segments),
            encoding="utf-8",
        )
        manifest_segments.append(
            {
                "segment_number": index,
                "start_line": segment["start_line"],
                "end_line": segment["end_line"],
                "char_count": len(str(segment["text"])),
                "source_path": str(source_path),
                "source_sha256": file_sha256(source_path),
                "prompt_path": str(prompt_path),
                "repaired_path": str(repaired_path),
            }
        )

    manifest = {
        "markdown_path": str(markdown_path),
        "markdown_sha256": file_sha256(markdown_path),
        "run_id": run_id,
        "segment_count": total_segments,
        "max_chars": max_chars,
        "segments": manifest_segments,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare segmented Markdown files for LLM readthrough repair.")
    parser.add_argument("markdown_path", help="Path to the generated Markdown file.")
    parser.add_argument("--output-dir", required=True, help="Directory for source segments, prompts, and repaired outputs.")
    parser.add_argument("--max-chars", type=int, default=12000, help="Target maximum characters per segment.")
    parser.add_argument("--run-id", help="Workflow run identifier stored in the segment manifest.")
    args = parser.parse_args()

    prepare_segments(
        Path(args.markdown_path).expanduser().resolve(),
        Path(args.output_dir).expanduser().resolve(),
        max_chars=args.max_chars,
        run_id=args.run_id,
    )
    print(f"Prepared LLM readthrough segments under {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
