from __future__ import annotations

import argparse
import json
from pathlib import Path

from pdf_workflow import parse_page_spec, record_visual_review


def load_list(path: str | None) -> list:
    if not path:
        return []
    payload = json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Record one completed visual segment review.")
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--segment", type=int, required=True)
    parser.add_argument("--pages", required=True, help="1-based pages, for example 1-12 or 11-20,22")
    parser.add_argument("--status", choices=("passed", "blocked"), required=True)
    parser.add_argument("--use-repaired", action="store_true", help="Copy repaired content when no visual edit is needed.")
    parser.add_argument("--changes-file", help="Optional JSON list describing confirmed corrections.")
    parser.add_argument("--unresolved-file", help="Optional JSON list describing unresolved source differences.")
    args = parser.parse_args()
    report = record_visual_review(
        Path(args.work_dir).expanduser().resolve(),
        segment_number=args.segment,
        pages_reviewed=parse_page_spec(args.pages),
        status=args.status,
        use_repaired=args.use_repaired,
        changes=load_list(args.changes_file),
        unresolved=load_list(args.unresolved_file),
    )
    print(f"Recorded visual review for segment {report['segment_number']}: {report['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
