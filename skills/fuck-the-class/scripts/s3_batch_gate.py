#!/usr/bin/env python3
"""Track S3 grading batches so retries never append attempt rows twice."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class BatchError(Exception):
    pass


BATCH_ID_RE = re.compile(r"^[0-9A-Za-z._-]+$")


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
        raise BatchError(f"无法读取批次日志：{exc}") from exc


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def manifest_path(course_root: Path, batch_id: str) -> Path:
    if not BATCH_ID_RE.fullmatch(batch_id):
        raise BatchError("batch_id 只能包含数字、英文字母、点、下划线和连字符")
    return course_root / "90_缓存" / "s3-grading" / f"{batch_id}.json"


def marker(batch_id: str) -> str:
    return f"<!-- s3-batch:{batch_id} -->"


def prepare(course_root: Path, batch_id: str, images: list[Path]) -> Path:
    course_root = course_root.resolve()
    path = manifest_path(course_root, batch_id)
    if path.exists():
        raise BatchError(f"批次已存在；读取并恢复，不得重新创建：{path}")
    inbox = (course_root / "30_我的数据" / "inbox").resolve()
    records = []
    for image in images:
        image = image.resolve()
        if not image.is_file():
            raise BatchError(f"inbox 图片不存在：{image}")
        try:
            image.relative_to(inbox)
        except ValueError as exc:
            raise BatchError(f"S3 输入必须位于 inbox：{image}") from exc
        records.append({"source": str(image), "sha256": sha256_file(image), "destination": None, "moved": False})
    if not records:
        raise BatchError("批次至少需要一张图片")
    payload = {
        "schema_version": 1,
        "batch_id": batch_id,
        "status": "prepared",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "records_marker": marker(batch_id),
        "images": records,
    }
    write_json(path, payload)
    return path


def marker_count(course_root: Path, expected: str) -> int:
    records = course_root / "30_我的数据" / "做题记录.md"
    if not records.exists():
        return 0
    return records.read_text(encoding="utf-8-sig").count(expected)


def mark_recorded(manifest: Path) -> None:
    payload = read_json(manifest)
    course_root = manifest.resolve().parents[2]
    count = marker_count(course_root, payload["records_marker"])
    if count != 1:
        raise BatchError(f"做题记录中的批次 marker 数量必须为 1，当前为 {count}")
    if payload["status"] not in {"prepared", "records_appended"}:
        raise BatchError(f"当前状态不能标记记录已追加：{payload['status']}")
    payload["status"] = "records_appended"
    payload["records_appended_at"] = datetime.now(timezone.utc).isoformat()
    write_json(manifest, payload)


def mark_moved(manifest: Path, source: Path, destination: Path) -> None:
    payload = read_json(manifest)
    if payload["status"] not in {"records_appended", "files_moving"}:
        raise BatchError("图片只能在做题记录确认追加后标记移动")
    course_root = manifest.resolve().parents[2]
    source, destination = source.resolve(), destination.resolve()
    match = next((row for row in payload["images"] if Path(row["source"]).resolve() == source), None)
    if match is None:
        raise BatchError(f"图片不属于该批次：{source}")
    archive = (course_root / "30_我的数据" / "archive").resolve()
    try:
        destination.relative_to(archive)
    except ValueError as exc:
        raise BatchError(f"S3 归档目标必须位于 archive：{destination}") from exc
    if source.exists() or not destination.is_file():
        raise BatchError("只有源文件已消失且归档文件存在时才能标记移动")
    if sha256_file(destination) != match.get("sha256"):
        raise BatchError("归档图片 SHA-256 与批次日志不一致")
    match["destination"] = str(destination)
    match["moved"] = True
    payload["status"] = "files_moving"
    write_json(manifest, payload)


def finalize(manifest: Path) -> None:
    payload = read_json(manifest)
    course_root = manifest.resolve().parents[2]
    if marker_count(course_root, payload["records_marker"]) != 1:
        raise BatchError("批次 marker 缺失或重复")
    for row in payload["images"]:
        if not row["moved"] or not row["destination"]:
            raise BatchError("仍有图片未归档")
        if Path(row["source"]).exists() or not Path(row["destination"]).is_file():
            raise BatchError("图片归档状态与批次日志不一致")
        if sha256_file(Path(row["destination"])) != row.get("sha256"):
            raise BatchError("归档图片 SHA-256 与批次日志不一致")
    payload["status"] = "complete"
    payload["completed_at"] = datetime.now(timezone.utc).isoformat()
    write_json(manifest, payload)


def verify(manifest: Path) -> None:
    payload = read_json(manifest)
    if payload.get("status") != "complete":
        raise BatchError(f"批次尚未完成，可从状态 {payload.get('status')} 恢复")
    course_root = manifest.resolve().parents[2]
    if marker_count(course_root, payload["records_marker"]) != 1:
        raise BatchError("批次 marker 缺失或重复")
    for row in payload["images"]:
        if Path(row["source"]).exists() or not Path(row["destination"]).is_file():
            raise BatchError("归档图片状态与 complete 批次不一致")
        if sha256_file(Path(row["destination"])) != row.get("sha256"):
            raise BatchError("归档图片 SHA-256 与 complete 批次不一致")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--course-root", required=True, type=Path)
    prepare_parser.add_argument("--batch-id", required=True)
    prepare_parser.add_argument("--image", required=True, action="append", type=Path)
    for name in ("mark-recorded", "finalize", "verify"):
        sub = commands.add_parser(name)
        sub.add_argument("--manifest", required=True, type=Path)
    moved = commands.add_parser("mark-moved")
    moved.add_argument("--manifest", required=True, type=Path)
    moved.add_argument("--source", required=True, type=Path)
    moved.add_argument("--destination", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "prepare":
            print(prepare(args.course_root, args.batch_id, args.image))
        elif args.command == "mark-recorded":
            mark_recorded(args.manifest)
        elif args.command == "mark-moved":
            mark_moved(args.manifest, args.source, args.destination)
        elif args.command == "finalize":
            finalize(args.manifest)
        else:
            verify(args.manifest)
    except BatchError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
