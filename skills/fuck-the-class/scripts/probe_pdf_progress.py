#!/usr/bin/env python3
"""Snapshot and compare pdf-to-markdown progress without taking ownership."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ProbeError(Exception):
    pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProbeError(f"无法读取 {path}：{exc}") from exc


def build_snapshot(work_dir: Path) -> dict[str, Any]:
    work_dir = work_dir.resolve()
    state_path = work_dir / "workflow_state.json"
    if not state_path.exists():
        raise ProbeError(f"缺少 workflow_state.json：{state_path}")
    state = read_json(state_path)
    review_dir = work_dir / "reports" / "visual_review" / "reviews"
    reviews: list[dict[str, Any]] = []
    for path in sorted(review_dir.glob("segment-*.json")) if review_dir.exists() else []:
        review = read_json(path)
        reviews.append({
            "segment_number": review.get("segment_number"),
            "status": review.get("status"),
            "pages_reviewed": review.get("pages_reviewed", []),
            "blockers": review.get("blockers", []),
            "reviewed_at": review.get("reviewed_at"),
            "file": path.name,
        })
    completed = [row for row in reviews if row["status"] == "passed"]
    pages = sorted({page for row in completed for page in row["pages_reviewed"]})
    review_blockers = sum(len(row.get("blockers", []) or []) for row in reviews)
    state_blockers = len(state.get("blockers", []) or [])
    unresolved_count = state.get("unresolved_count", 0)
    if not isinstance(unresolved_count, int):
        unresolved_count = 0
    return {
        "snapshot_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "work_dir": str(work_dir),
        "run_id": state.get("run_id"),
        "status": state.get("status"),
        "updated_at": state.get("updated_at"),
        "completed_segment_count": len(completed),
        "completed_segments": [row["segment_number"] for row in completed],
        "reviewed_page_count": len(pages),
        "reviewed_pages": pages,
        "review_count": len(reviews),
        "blocker_count": state_blockers + review_blockers,
        "unresolved_count": unresolved_count,
    }


def compare_snapshots(before: dict[str, Any], after: dict[str, Any]) -> tuple[bool, list[str]]:
    if before.get("work_dir") != after.get("work_dir"):
        raise ProbeError("两次快照不是同一工作目录")
    if before.get("run_id") != after.get("run_id"):
        raise ProbeError("run_id 已变化，不能当作同一轮进度比较")
    reasons: list[str] = []
    if before.get("status") != after.get("status"):
        reasons.append(f"状态 {before.get('status')} -> {after.get('status')}")
    if after.get("completed_segment_count", 0) > before.get("completed_segment_count", 0):
        reasons.append(
            f"完成分段 {before.get('completed_segment_count', 0)} -> {after.get('completed_segment_count', 0)}"
        )
    if after.get("reviewed_page_count", 0) > before.get("reviewed_page_count", 0):
        reasons.append(f"核对页数 {before.get('reviewed_page_count', 0)} -> {after.get('reviewed_page_count', 0)}")
    if after.get("review_count", 0) > before.get("review_count", 0):
        reasons.append(f"review 记录 {before.get('review_count', 0)} -> {after.get('review_count', 0)}")
    return bool(reasons), reasons


def write_snapshot(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    snapshot = subparsers.add_parser("snapshot")
    snapshot.add_argument("--work-dir", required=True, type=Path)
    snapshot.add_argument("--output", required=True, type=Path)
    compare = subparsers.add_parser("compare")
    compare.add_argument("--before", required=True, type=Path)
    compare.add_argument("--after", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "snapshot":
            payload = build_snapshot(args.work_dir)
            write_snapshot(args.output, payload)
            print(
                f"PDF 进度快照：状态 {payload['status']}，完成分段 {payload['completed_segment_count']}，"
                f"核对页数 {payload['reviewed_page_count']}，blocker {payload['blocker_count']}，"
                f"未决 {payload['unresolved_count']}"
            )
            return 0
        progressed, reasons = compare_snapshots(read_json(args.before), read_json(args.after))
    except ProbeError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    if progressed:
        print("PDF 转换有进展：" + "；".join(reasons))
        return 0
    print("PDF 转换无可确认的实质进展")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
