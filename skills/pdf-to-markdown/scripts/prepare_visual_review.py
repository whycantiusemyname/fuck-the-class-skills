from __future__ import annotations

import argparse
from pathlib import Path

from pdf_workflow import prepare_visual_review


def main() -> int:
    parser = argparse.ArgumentParser(description="Render PDF pages and prepare visual verification records.")
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    manifest = prepare_visual_review(
        Path(args.work_dir).expanduser().resolve(),
        dpi=args.dpi,
        reset=args.reset,
    )
    print(f"Prepared {manifest['page_count']} rendered pages for visual review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
