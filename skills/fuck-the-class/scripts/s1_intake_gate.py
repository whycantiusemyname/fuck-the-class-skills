#!/usr/bin/env python3
"""Bind and verify S1 PDF intake outputs against a certified Markdown source."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import analyze_frequency_trends as analyzer
import validate_course_artifacts as course_validator


SCHEMA_VERSION = "1.0"
FORBIDDEN_NAMES = {"draft.md"}
FORBIDDEN_PARTS = {"source", "repaired"}


class IntakeError(Exception):
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
        raise IntakeError(f"无法读取 JSON：{path}：{exc}") from exc


def certified_markdown_allowed(path: Path) -> bool:
    lowered_parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    return (
        name not in FORBIDDEN_NAMES
        and not name.endswith(".mineru.md")
        and not (FORBIDDEN_PARTS & lowered_parts)
    )


def default_pdf_skill() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return codex_home / "skills" / "pdf-to-markdown"


def run_completion_verifier(completion: Path, pdf_skill: Path) -> None:
    verifier = pdf_skill / "scripts" / "verify_completion.py"
    if not verifier.exists():
        raise IntakeError(f"找不到 PDF completion verifier：{verifier}")
    result = subprocess.run(
        [sys.executable, str(verifier), "--work-dir", str(completion.parent)],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise IntakeError(f"PDF completion 验证失败：{detail}")


def question_anchors(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    anchors: list[str] = []
    for index, line in enumerate(lines):
        match = re.match(r"^###\s+(.+?)\s*$", line)
        if not match:
            continue
        metadata = analyzer.parse_metadata_block(lines, index)
        if not metadata or not {"chapter", "question_type", "source"} <= metadata.keys():
            continue
        if metadata.get("question_type", "").startswith("真题整卷"):
            continue
        anchors.append(match.group(1).strip())
    if not anchors:
        raise IntakeError(f"题库输出没有可绑定题目锚点：{path}")
    return anchors


def relative_or_absolute(path: Path, course_root: Path) -> str:
    try:
        return path.resolve().relative_to(course_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def validate_completion_identity(source: Path, completion: Path) -> tuple[dict[str, Any], Path]:
    payload = read_json(completion)
    if payload.get("status") != "complete":
        raise IntakeError("completion.json 状态不是 complete")
    recorded_source = Path(payload.get("source_pdf", "")).resolve()
    if recorded_source != source.resolve():
        raise IntakeError("completion.json 的 source_pdf 与 S1 输入不一致")
    if sha256_file(source) != payload.get("source_pdf_sha256"):
        raise IntakeError("源 PDF SHA-256 与 completion.json 不一致")
    final_markdown = Path(payload.get("final_markdown", "")).resolve()
    if not final_markdown.is_file():
        raise IntakeError("认证 Markdown 不存在")
    if not certified_markdown_allowed(final_markdown):
        raise IntakeError(f"拒绝消费未认证中间产物：{final_markdown}")
    if sha256_file(final_markdown) != payload.get("final_markdown_sha256"):
        raise IntakeError("认证 Markdown SHA-256 与 completion.json 不一致")
    if payload.get("unresolved_count") != 0:
        raise IntakeError("completion.json 仍有未决问题")
    return payload, final_markdown


def manifest_path_for(course_root: Path, source: Path) -> Path:
    return course_root / "90_缓存" / "s1-intake" / source.stem / "intake.json"


def find_duplicate_source(course_root: Path, source_hash: str, target: Path) -> Path | None:
    root = course_root / "90_缓存" / "s1-intake"
    if not root.exists():
        return None
    for path in root.rglob("intake.json"):
        if path.resolve() == target.resolve():
            continue
        try:
            payload = read_json(path)
        except IntakeError:
            continue
        if payload.get("status") == "complete" and payload.get("source", {}).get("sha256") == source_hash:
            return path
    return None


def bind_manifest(
    course_root: Path,
    source: Path,
    completion: Path,
    outputs: list[Path],
    pdf_skill: Path | None = None,
    *,
    run_external: bool = True,
) -> Path:
    course_root, source, completion = course_root.resolve(), source.resolve(), completion.resolve()
    if not source.is_file() or not completion.is_file():
        raise IntakeError("源 PDF 或 completion.json 不存在")
    if run_external:
        run_completion_verifier(completion, (pdf_skill or default_pdf_skill()).resolve())
    completion_payload, final_markdown = validate_completion_identity(source, completion)
    output_records: list[dict[str, Any]] = []
    all_anchors: list[str] = []
    seen: set[str] = set()
    qbank_root = (course_root / "10_题库").resolve()
    for output in outputs:
        output = output.resolve()
        if not output.is_file():
            raise IntakeError(f"题库输出不存在：{output}")
        try:
            output.relative_to(qbank_root)
        except ValueError as exc:
            raise IntakeError(f"S1 输出必须位于 10_题库：{output}") from exc
        anchors = question_anchors(output)
        duplicates = sorted(set(anchors) & seen)
        if duplicates:
            raise IntakeError(f"S1 输出之间存在重复锚点：{duplicates}")
        seen.update(anchors)
        all_anchors.extend(anchors)
        output_records.append({
            "path": relative_or_absolute(output, course_root),
            "sha256": sha256_file(output),
            "anchors": anchors,
        })
    self_errors, _, self_counts = course_validator.validate(course_root, "s1")
    if self_errors:
        raise IntakeError("S1 Output Self-Check 失败：" + "; ".join(self_errors[:5]))
    target = manifest_path_for(course_root, source)
    if target.exists():
        raise IntakeError(f"当前源文件已有 intake manifest：{target}")
    source_hash = sha256_file(source)
    duplicate = find_duplicate_source(course_root, source_hash, target)
    if duplicate:
        raise IntakeError(f"相同源 PDF 已完成入库绑定：{duplicate}")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {"path": str(source), "sha256": source_hash},
        "completion": {"path": str(completion), "sha256": sha256_file(completion)},
        "certified_markdown": {
            "path": str(final_markdown),
            "sha256": completion_payload["final_markdown_sha256"],
        },
        "outputs": output_records,
        "anchor_count": len(all_anchors),
        "anchors": all_anchors,
        "self_check": {
            "control_characters": self_counts["control"],
            "latex_issues": self_counts["latex"],
            "broken_links": self_counts["links"],
        },
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(target)
    verify_manifest(target)
    return target


def verify_manifest(manifest_path: Path) -> None:
    manifest_path = manifest_path.resolve()
    payload = read_json(manifest_path)
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("status") != "complete":
        raise IntakeError("intake manifest schema/status 无效")
    for key in ("source", "completion", "certified_markdown"):
        record = payload.get(key, {})
        path = Path(record.get("path", "")).resolve()
        if not path.is_file() or sha256_file(path) != record.get("sha256"):
            raise IntakeError(f"intake manifest 的 {key} 哈希失配")
    final_path = Path(payload["certified_markdown"]["path"])
    if not certified_markdown_allowed(final_path):
        raise IntakeError("intake manifest 指向被禁止的中间 Markdown")
    all_anchors: list[str] = []
    for record in payload.get("outputs", []):
        raw_path = Path(record.get("path", ""))
        course_root = manifest_path.parents[3]
        path = raw_path if raw_path.is_absolute() else course_root / raw_path
        path = path.resolve()
        if not path.is_file() or sha256_file(path) != record.get("sha256"):
            raise IntakeError(f"题库输出哈希失配：{path}")
        anchors = question_anchors(path)
        if anchors != record.get("anchors"):
            raise IntakeError(f"题库输出锚点与 manifest 不一致：{path}")
        all_anchors.extend(anchors)
    if len(all_anchors) != len(set(all_anchors)):
        raise IntakeError("intake manifest 中存在重复锚点")
    if all_anchors != payload.get("anchors") or len(all_anchors) != payload.get("anchor_count"):
        raise IntakeError("intake manifest 的总锚点清单不一致")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    bind = subparsers.add_parser("bind")
    bind.add_argument("--course-root", required=True, type=Path)
    bind.add_argument("--source", required=True, type=Path)
    bind.add_argument("--completion", required=True, type=Path)
    bind.add_argument("--output", required=True, action="append", type=Path)
    bind.add_argument("--pdf-skill", type=Path)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--manifest", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "bind":
            path = bind_manifest(args.course_root, args.source, args.completion, args.output, args.pdf_skill)
            print(f"S1 intake manifest 已绑定：{path}")
        else:
            verify_manifest(args.manifest)
            print("S1 intake manifest 验证通过")
    except (IntakeError, course_validator.ValidationConfigError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
