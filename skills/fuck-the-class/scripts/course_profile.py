#!/usr/bin/env python3
"""Create and validate the optional course-level learning and scope profile."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


PROFILE_NAME = "课程口径.md"
REQUIRED_SECTIONS = (
    "学习阶段",
    "已确认教学/考试范围",
    "教师重点与主线/补充关系",
    "明确排除内容",
)


class CourseProfileError(Exception):
    pass


def profile_path(course_root: Path) -> Path:
    return course_root.resolve() / PROFILE_NAME


def normalize_learning_stage(value: str | None) -> str:
    stage = (value or "未设置").strip()
    if not stage or "\n" in stage or "\r" in stage:
        raise CourseProfileError("学习阶段必须是单行非空文本；未提供时使用“未设置”")
    return stage


def render_list(values: list[str] | None) -> str:
    cleaned = [value.strip() for value in values or [] if value.strip()]
    return "\n".join(f"- {value}" for value in cleaned) if cleaned else "未设置"


def render_profile(
    learning_stage: str | None = None,
    confirmed_scope: list[str] | None = None,
    teacher_emphasis: list[str] | None = None,
    exclusions: list[str] | None = None,
) -> str:
    return (
        "# 课程口径\n\n"
        "> 本文件记录课程层次与已确认范围。学习阶段只调整解释方式和默认前置知识，不扩大课程内容边界。\n\n"
        "## 学习阶段\n\n"
        f"{normalize_learning_stage(learning_stage)}\n\n"
        "## 已确认教学/考试范围\n\n"
        f"{render_list(confirmed_scope)}\n\n"
        "## 教师重点与主线/补充关系\n\n"
        f"{render_list(teacher_emphasis)}\n\n"
        "## 明确排除内容\n\n"
        f"{render_list(exclusions)}\n"
    )


def parse_profile(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise CourseProfileError(f"无法读取课程口径：{exc}") from exc
    if not re.search(r"^#\s+课程口径\s*$", text, flags=re.MULTILINE):
        raise CourseProfileError("课程口径缺少一级标题“# 课程口径”")
    headings = list(re.finditer(r"^##\s+(.+?)\s*$", text, flags=re.MULTILINE))
    values: dict[str, str] = {}
    for index, match in enumerate(headings):
        name = match.group(1).strip()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = text[match.end() : end].strip()
        if name in REQUIRED_SECTIONS:
            if name in values:
                raise CourseProfileError(f"课程口径章节重复：{name}")
            values[name] = body
    missing = [name for name in REQUIRED_SECTIONS if name not in values]
    if missing:
        raise CourseProfileError(f"课程口径缺少章节：{', '.join(missing)}")
    empty = [name for name, value in values.items() if not value]
    if empty:
        raise CourseProfileError(f"课程口径章节为空：{', '.join(empty)}")
    stage_lines = [line.strip() for line in values["学习阶段"].splitlines() if line.strip()]
    if len(stage_lines) != 1:
        raise CourseProfileError("学习阶段必须是单行非空文本或“未设置”")
    values["学习阶段"] = stage_lines[0]
    return values


def load_profile(course_root: Path) -> dict[str, str] | None:
    path = profile_path(course_root)
    return parse_profile(path) if path.exists() else None


def scope_fields(profile: dict[str, str] | None) -> dict[str, str]:
    if profile is None:
        return {name: "未设置" for name in REQUIRED_SECTIONS[1:]}
    return {name: profile[name] for name in REQUIRED_SECTIONS[1:]}


def initialize(
    course_root: Path,
    learning_stage: str | None,
    confirmed_scope: list[str],
    teacher_emphasis: list[str],
    exclusions: list[str],
    replace: bool,
) -> Path:
    course_root = course_root.resolve()
    if not course_root.is_dir():
        raise CourseProfileError(f"课程目录不存在：{course_root}")
    path = profile_path(course_root)
    if path.exists() and not replace:
        raise CourseProfileError(f"课程口径已存在；更新时显式使用 --replace：{path}")
    temporary = path.with_suffix(".md.tmp")
    temporary.write_text(
        render_profile(learning_stage, confirmed_scope, teacher_emphasis, exclusions),
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)
    parse_profile(path)
    return path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init_parser = commands.add_parser("init")
    init_parser.add_argument("--course-root", required=True, type=Path)
    init_parser.add_argument("--learning-stage")
    init_parser.add_argument("--confirmed-scope", action="append", default=[])
    init_parser.add_argument("--teacher-emphasis", action="append", default=[])
    init_parser.add_argument("--exclude", action="append", default=[])
    init_parser.add_argument("--replace", action="store_true")
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--course-root", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "init":
            path = initialize(
                args.course_root,
                args.learning_stage,
                args.confirmed_scope,
                args.teacher_emphasis,
                args.exclude,
                args.replace,
            )
            print(path)
        else:
            profile = load_profile(args.course_root)
            if profile is None:
                print("课程口径未设置；兼容模式：以用户提供的课程材料为边界")
            else:
                print(f"课程口径验证通过：学习阶段={profile['学习阶段']}")
    except CourseProfileError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
