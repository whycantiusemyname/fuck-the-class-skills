#!/usr/bin/env python3
"""Bind and verify S8 courseware sources, certificates, and knowledge outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import lint_s8_chapter_docs


class DigestError(Exception):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(path: Path, course_root: Path) -> dict[str, str]:
    path = path.resolve()
    if not path.is_file():
        raise DigestError(f"文件不存在：{path}")
    try:
        stored = path.relative_to(course_root.resolve()).as_posix()
    except ValueError:
        stored = str(path)
    return {"path": stored, "sha256": sha256_file(path)}


def safe_chapter(chapter: str) -> str:
    value = re.sub(r"[<>:\"/\\|?*]+", "_", chapter).strip(" .")
    if not value:
        raise DigestError("章节名不能生成有效 manifest 路径")
    return value


def resolve_record(course_root: Path, item: dict[str, str]) -> Path:
    path = Path(item["path"])
    return path.resolve() if path.is_absolute() else (course_root / path).resolve()


def resolve_completion_markdown(course_root: Path, completion: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    completion_relative = (completion.parent / path).resolve()
    if completion_relative.is_file():
        return completion_relative
    return (course_root / path).resolve()


def bind(
    course_root: Path,
    chapter: str,
    sources: list[Path],
    completions: list[Path],
    outputs: list[Path],
    replace: bool = False,
    mode: str = "default",
) -> Path:
    course_root = course_root.resolve()
    target = course_root / "90_缓存" / "s8-digest" / safe_chapter(chapter) / "digest.json"
    if target.exists() and not replace:
        raise DigestError(f"digest manifest 已存在；刷新时显式使用 --replace：{target}")
    if not sources or not outputs:
        raise DigestError("S8 manifest 至少需要一个源文件和一个输出文件")
    warnings: list[str] = []
    completion_records = []
    for completion in completions:
        payload = json.loads(completion.read_text(encoding="utf-8-sig"))
        if payload.get("status") != "complete" or payload.get("unresolved_count") != 0:
            raise DigestError(f"无效 completion.json：{completion}")
        completion_records.append(record(completion, course_root))
        final = resolve_completion_markdown(course_root, completion, payload.get("final_markdown", ""))
        if not final.is_file() or sha256_file(final) != payload.get("final_markdown_sha256"):
            raise DigestError(f"completion 的认证 Markdown 哈希失配：{completion}")
    knowledge_root = (course_root / "20_知识").resolve()
    output_records = []
    lint_report = lint_s8_chapter_docs.LintReport()
    for output in outputs:
        output = output.resolve()
        try:
            output.relative_to(knowledge_root)
        except ValueError as exc:
            raise DigestError(f"S8 输出必须位于 20_知识：{output}") from exc
        output_records.append(record(output, course_root))
    lint_report.extend(lint_s8_chapter_docs.lint_files([path.resolve() for path in outputs], mode=mode))
    if lint_report.errors:
        raise DigestError("\n".join(lint_report.errors))
    warnings.extend(lint_report.warnings)
    raw_root = (course_root / "00_原材料").resolve()
    source_records = []
    for source in sources:
        source_record = record(source, course_root)
        source_records.append(source_record)
        try:
            source.resolve().relative_to(raw_root)
        except ValueError:
            warnings.append(f"S8 源文件不在 00_原材料：{source_record['path']}")
    payload = {
        "schema_version": 1,
        "status": "complete",
        "chapter": chapter,
        "mode": mode,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sources": source_records,
        "completions": completion_records,
        "outputs": output_records,
        "warnings": warnings,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(target)
    verify(target)
    return target


def verify(manifest: Path) -> None:
    manifest = manifest.resolve()
    try:
        payload: dict[str, Any] = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DigestError(f"无法读取 digest manifest：{exc}") from exc
    if payload.get("status") != "complete" or payload.get("schema_version") != 1:
        raise DigestError("digest manifest schema/status 无效")
    course_root = manifest.parents[3]
    for group in ("sources", "completions", "outputs"):
        for item in payload.get(group, []):
            path = resolve_record(course_root, item)
            if not path.is_file() or sha256_file(path) != item.get("sha256"):
                raise DigestError(f"digest manifest 哈希失配：{path}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    bind_parser = commands.add_parser("bind")
    bind_parser.add_argument("--course-root", required=True, type=Path)
    bind_parser.add_argument("--chapter", required=True)
    bind_parser.add_argument("--source", required=True, action="append", type=Path)
    bind_parser.add_argument("--completion", action="append", default=[], type=Path)
    bind_parser.add_argument("--output", required=True, action="append", type=Path)
    bind_parser.add_argument("--mode", choices=("default", "grounding-only", "quick-start-only"), default="default")
    bind_parser.add_argument("--replace", action="store_true")
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--manifest", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "bind":
            print(bind(args.course_root, args.chapter, args.source, args.completion, args.output, replace=args.replace, mode=args.mode))
        else:
            verify(args.manifest)
            print("S8 digest manifest 验证通过")
    except (DigestError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
