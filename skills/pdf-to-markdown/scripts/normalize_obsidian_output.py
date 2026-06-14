from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

from mineru_common import ensure_dir
from PIL import Image, UnidentifiedImageError

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"}
MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
HTML_IMAGE_RE = re.compile(r'<img\b[^>]*src=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)
OBSIDIAN_EMBED_RE = re.compile(r"!\[\[([^\]]+)\]\]")


def find_full_markdown(extract_dir: Path) -> Path | None:
    candidates = [path for path in extract_dir.rglob("full.md") if path.is_file()]
    if not candidates:
        return None
    return sorted(candidates)[0]


def list_assets(extract_dir: Path) -> list[Path]:
    return sorted(
        [
            path
            for path in extract_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        ]
    )


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip() + "\n"


def repair_bracket_math_blocks(text: str) -> str:
    math_markers = ("\\", "_", "^", "\\times", "\\mathrm", "\\text", "=")
    pattern = re.compile(r"^[ \t]*\[[ \t]*(.+?)[ \t]*\][ \t]*$", re.MULTILINE)

    def replace(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        if inner and any(marker in inner for marker in math_markers):
            return f"$$\n{inner}\n$$"
        return match.group(0)

    return pattern.sub(replace, text)


def repair_latex_math_delimiters(text: str) -> str:
    text = re.sub(
        r"\\\(\s*(.+?)\s*\\\)",
        lambda match: f"${match.group(1).strip()}$",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"\\\[\s*(.+?)\s*\\\]",
        lambda match: "$$\n" + match.group(1).strip() + "\n$$",
        text,
        flags=re.DOTALL,
    )
    return text


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


def format_obsidian_embed(path: str, image_width: int | None) -> str:
    if image_width is not None:
        return f"![[{path}|{image_width}]]"
    return f"![[{path}]]"


def rewrite_image_links(
    text: str,
    asset_map: dict[str, str],
    embed_widths: dict[str, int | None],
    image_width: int | None = None,
) -> str:
    def replace_obsidian(match: re.Match[str]) -> str:
        original = match.group(1).strip()
        key = Path(original).name
        renamed = asset_map.get(key)
        if not renamed:
            return match.group(0)
        return format_obsidian_embed(renamed, embed_widths.get(key, image_width))

    text = OBSIDIAN_EMBED_RE.sub(replace_obsidian, text)
    if OBSIDIAN_EMBED_RE.search(text):
        return text

    def replace_markdown(match: re.Match[str]) -> str:
        original = match.group(2).strip()
        key = Path(original).name
        renamed = asset_map.get(key)
        if not renamed:
            return match.group(0)
        return format_obsidian_embed(renamed, embed_widths.get(key, image_width))

    text = MARKDOWN_IMAGE_RE.sub(replace_markdown, text)

    def replace_html(match: re.Match[str]) -> str:
        original = match.group(1).strip()
        key = Path(original).name
        renamed = asset_map.get(key)
        if not renamed:
            return match.group(0)
        return format_obsidian_embed(renamed, embed_widths.get(key, image_width))

    return HTML_IMAGE_RE.sub(replace_html, text)


def normalize_chunk(
    extract_dir: Path,
    output_md: Path,
    metadata_path: Path,
    assets_root: Path,
    *,
    note_stem: str,
    start_page: int,
    end_page: int,
    image_width: int | None = None,
) -> tuple[Path, Path]:
    full_md = find_full_markdown(extract_dir)
    if full_md is None:
        raise FileNotFoundError(f"Could not find full.md under {extract_dir}")

    raw_text = full_md.read_text(encoding="utf-8")

    assets_dir = ensure_dir(assets_root / note_stem)
    asset_map: dict[str, str] = {}
    embed_widths: dict[str, int | None] = {}
    for index, asset in enumerate(list_assets(extract_dir), start=1):
        renamed = f"p{start_page:04d}-{end_page:04d}_{index:03d}{asset.suffix.lower()}"
        destination = assets_dir / renamed
        shutil.copy2(asset, destination)
        asset_map[asset.name] = f"assets/{note_stem}/{renamed}"
        embed_widths[asset.name] = choose_embed_width(destination, image_width)

    normalized = normalize_newlines(raw_text)
    normalized = repair_bracket_math_blocks(normalized)
    normalized = repair_latex_math_delimiters(normalized)
    normalized = rewrite_image_links(normalized, asset_map, embed_widths, image_width=image_width)

    boundary = f"<!-- pdf-to-markdown pages {start_page}-{end_page} -->\n\n"
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(boundary + normalized, encoding="utf-8")

    metadata_payload = {
        "chunk_range": [start_page, end_page],
        "full_md": str(full_md),
        "mode": "pass-through",
        "asset_count": len(asset_map),
        "llm_readthrough_required": True,
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_md, metadata_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize one extracted MinerU result into Obsidian-friendly Markdown.")
    parser.add_argument("extract_dir", help="Directory created by extracting the MinerU result zip.")
    parser.add_argument("--output-md", required=True, help="Destination Markdown chunk path.")
    parser.add_argument("--metadata-path", required=True, help="Destination JSON metadata path.")
    parser.add_argument("--assets-root", required=True, help="Root directory that will contain assets/<note-stem>/")
    parser.add_argument("--note-stem", required=True, help="Note stem used for assets/<note-stem>/")
    parser.add_argument("--start-page", required=True, type=int)
    parser.add_argument("--end-page", required=True, type=int)
    parser.add_argument("--image-width", type=int, help="Optional Obsidian image width to append as |WIDTH.")
    args = parser.parse_args()

    normalize_chunk(
        Path(args.extract_dir).expanduser().resolve(),
        Path(args.output_md).expanduser().resolve(),
        Path(args.metadata_path).expanduser().resolve(),
        Path(args.assets_root).expanduser().resolve(),
        note_stem=args.note_stem,
        start_page=args.start_page,
        end_page=args.end_page,
        image_width=args.image_width,
    )
    print(f"Normalized chunk to {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
