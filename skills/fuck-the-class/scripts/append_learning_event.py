#!/usr/bin/env python3
"""Append one normalized S10 learning event to a course JSONL ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

EVENT_TYPES = {"attempt", "question", "explanation", "probe", "repair", "variant", "reflection", "state_update"}
ORIGINS = {"s3", "s10", "manual", "import"}
CREATED_BY = {"main_agent", "subagent", "user", "script"}
OUTCOMES = {
    "not_tested",
    "observed",
    "repaired_independently",
    "repaired_with_hint",
    "needs_followup",
    "not_repaired",
    "deferred",
}
CONFIDENCE = {"low", "medium", "high"}
JUDGEMENTS = {"对", "对但慢", "卡", "错", "空"}
WRONG_CAUSES = {"概念错", "起手错", "计算错", "审题错", "没思路"}
S3_FORBIDDEN_FIELDS = {"diagnosis_hypothesis", "next_probe", "tutor_action", "hint_level"}


class EventError(Exception):
    pass


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def load_event(args: argparse.Namespace) -> dict[str, Any]:
    if bool(args.event_json) == bool(args.event_file):
        raise EventError("必须且只能提供 --event-json 或 --event-file")
    if args.event_file:
        raw = read_text(args.event_file)
    else:
        raw = args.event_json
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EventError(f"事件不是合法 JSON：{exc.msg}") from exc
    if not isinstance(payload, dict):
        raise EventError("事件 JSON 必须是对象")
    return payload


def signature_for(event: dict[str, Any]) -> str:
    parts = [
        str(event.get("event_type", "")),
        str(event.get("anchor", "")),
        str(event.get("diagnosis_hypothesis", "")),
        str(event.get("evidence", "")),
        str(event.get("next_probe", "")),
    ]
    return hashlib.sha256("\u241f".join(parts).encode("utf-8")).hexdigest()[:16]


def existing_signatures(path: Path) -> set[str]:
    if not path.exists():
        return set()
    signatures: set[str] = set()
    for line in read_text(path).splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and isinstance(item.get("event_signature"), str):
            signatures.add(item["event_signature"])
        elif isinstance(item, dict):
            signatures.add(signature_for(item))
    return signatures


def next_event_id(now: datetime, event: dict[str, Any]) -> str:
    base = now.strftime("%Y%m%d-%H%M%S")
    digest = hashlib.sha256(json.dumps(event, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:6]
    return f"{base}-{digest}"


def normalize_event(event: dict[str, Any], *, now: datetime) -> dict[str, Any]:
    event = dict(event)
    event.setdefault("time", now.astimezone().isoformat(timespec="seconds"))
    event.setdefault("origin", "s10")
    if event.get("origin") == "s10":
        event.setdefault("created_by", "main_agent")
    elif event.get("origin") == "s3":
        event.setdefault("created_by", "script")
    else:
        event.setdefault("created_by", "user")
    event.setdefault("outcome", "observed")
    event["event_signature"] = event.get("event_signature") or signature_for(event)
    event.setdefault("event_id", next_event_id(now, event))
    return event


def validate_event(event: dict[str, Any]) -> None:
    missing = {"event_id", "time", "event_type", "origin", "evidence"} - event.keys()
    if missing:
        raise EventError(f"缺少必填字段：{sorted(missing)}")
    if event["event_type"] not in EVENT_TYPES:
        raise EventError(f"event_type 不在允许集合中：{event['event_type']}")
    if event["origin"] not in ORIGINS:
        raise EventError(f"origin 不在允许集合中：{event['origin']}")
    if event.get("created_by") not in CREATED_BY:
        raise EventError(f"created_by 不在允许集合中：{event.get('created_by')}")
    if event.get("outcome") not in OUTCOMES:
        raise EventError(f"outcome 不在允许集合中：{event.get('outcome')}")
    try:
        datetime.fromisoformat(str(event["time"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise EventError(f"time 不是 ISO 8601 时间：{event['time']}") from exc
    if not isinstance(event.get("evidence"), str) or not event["evidence"].strip():
        raise EventError("evidence 必须是非空字符串")
    if event["origin"] == "s3":
        if event["event_type"] != "attempt":
            raise EventError("origin=s3 只能写 attempt 事件")
        forbidden = sorted(field for field in S3_FORBIDDEN_FIELDS if field in event)
        if forbidden:
            raise EventError(f"origin=s3 不得主动写 S10 字段：{forbidden}")
    if "confidence" in event and event["confidence"] not in CONFIDENCE:
        raise EventError(f"confidence 不在允许集合中：{event['confidence']}")
    if "judgement" in event:
        if event["event_type"] != "attempt":
            raise EventError("非 attempt 事件不得写 judgement")
        if event["judgement"] not in JUDGEMENTS:
            raise EventError(f"judgement 不在允许集合中：{event['judgement']}")
    if "coarse_wrong_cause" in event:
        if event["event_type"] != "attempt":
            raise EventError("非 attempt 事件不得写 coarse_wrong_cause")
        if event["coarse_wrong_cause"] not in WRONG_CAUSES:
            raise EventError(f"coarse_wrong_cause 不在允许集合中：{event['coarse_wrong_cause']}")
    if event.get("diagnosis_hypothesis") and (not event.get("confidence") or not event.get("next_probe")):
        raise EventError("diagnosis_hypothesis 需要同时写 confidence 和 next_probe")
    source_refs = event.get("source_refs")
    if source_refs is not None:
        if not isinstance(source_refs, list) or any(not isinstance(ref, str) for ref in source_refs):
            raise EventError("source_refs 必须是字符串数组")


def append_event(course_root: Path, event: dict[str, Any], *, dedupe: bool = True) -> tuple[str, Path]:
    course_root = course_root.resolve()
    if not course_root.is_dir():
        raise EventError(f"课程目录不存在：{course_root}")
    events_path = course_root / "30_我的数据" / "学习事件.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    if dedupe and event["event_signature"] in existing_signatures(events_path):
        return "skipped_duplicate", events_path
    with events_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=False) + "\n")
    return "appended", events_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--course-root", required=True, type=Path)
    parser.add_argument("--event-json")
    parser.add_argument("--event-file", type=Path)
    parser.add_argument("--no-dedupe", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        event = normalize_event(load_event(args), now=datetime.now().astimezone())
        validate_event(event)
        status, path = append_event(args.course_root, event, dedupe=not args.no_dedupe)
    except EventError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"{status}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
