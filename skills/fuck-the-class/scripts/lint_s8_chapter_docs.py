#!/usr/bin/env python3
"""Lint S8 chapter documents so starter/grounding files cannot replace the main explanation."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


class ChapterDocsLintError(Exception):
    pass


@dataclass
class LintReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def extend(self, other: "LintReport") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


MAIN_REQUIRED_HEADING_GROUPS = (
    ("章节主线", ("这一章抓什么", "这一章的核心问题", "本章放在课程里的位置")),
    ("整体直觉", ("先建立整体直觉", "先建立整体图像", "整体直觉", "整体图像")),
    ("本章串联", ("本章怎么串起来", "本章主线图", "本章总图")),
    ("分节主干", ("分节主干", "核心讲解节", "核心主题", "核心主干")),
    ("解题或题型入口", ("解题流程", "典型题型入口", "题型入口", "题目入口")),
    ("易错提醒", ("易错点", "常见误判", "常见坑", "易错提醒")),
    ("复习检查", ("复习检查", "自测检查")),
)

S10_ENTRY_HEADINGS = (
    "进入 S10 的问题入口",
    "进入 S10",
    "提问入口",
)

FIXED_CORE_TEMPLATE_HEADINGS = (
    "直觉",
    "公式 / 条件",
    "公式为什么这样",
    "题目怎么起手",
    "易错点",
)

START_REQUIRED_TEXT = (
    "不替代",
    "主干讲解",
)

OLD_CHECKLIST_SIGNALS = (
    "这章一句话",
    "你先只需要会的三件事",
    "一个 30 秒 probe",
)

ROLE_SUFFIXES = (
    ("main", "_主干讲解.md"),
    ("grounding", "_grounding.md"),
    ("start", "_S10启动卡.md"),
    ("legacy_main", "_主干重点.md"),
    ("legacy_starter", "_入门讲解.md"),
    ("quick", "_速查卡.md"),
)

BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)]|[一二三四五六七八九十]+[、.])\s+")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
DISPLAY_MATH_RE = re.compile(r"(\$\$.*?\$\$|\\\[.*?\\\])", re.DOTALL)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def classify(path: Path) -> str | None:
    name = path.name
    for role, suffix in ROLE_SUFFIXES:
        if name.endswith(suffix):
            return role
    return None


def chapter_key(path: Path) -> str:
    name = path.name
    for _, suffix in ROLE_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def has_heading(text: str, heading: str) -> bool:
    for match in HEADING_RE.finditer(text):
        normalized = re.sub(r"\s+", "", match.group(1))
        target = re.sub(r"\s+", "", heading)
        if target in normalized:
            return True
    return False


def heading_titles(text: str) -> list[str]:
    return [match.group(1).strip() for match in HEADING_RE.finditer(text)]


def normalize_heading(value: str) -> str:
    return re.sub(r"[\s`/／：:、，,。.!！?？（）()]+", "", value)


def heading_matches(title: str, target: str) -> bool:
    return normalize_heading(target) in normalize_heading(title)


def has_any_heading(text: str, headings: tuple[str, ...]) -> bool:
    return any(has_heading(text, heading) for heading in headings)


def fixed_template_sequence_count(text: str) -> int:
    titles = heading_titles(text)
    count = 0
    size = len(FIXED_CORE_TEMPLATE_HEADINGS)
    for index in range(0, max(0, len(titles) - size + 1)):
        window = titles[index : index + size]
        if all(heading_matches(title, target) for title, target in zip(window, FIXED_CORE_TEMPLATE_HEADINGS)):
            count += 1
    return count


def cjk_count(text: str) -> int:
    return len(CJK_RE.findall(text))


def is_content_line(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith("#") and not stripped.startswith("> [!")


def bullet_stats(text: str) -> tuple[int, int, int]:
    bullet_lines = 0
    content_lines = 0
    current = 0
    maximum = 0
    for line in text.splitlines():
        if not is_content_line(line):
            if line.strip():
                current = 0
            continue
        content_lines += 1
        if BULLET_RE.match(line):
            bullet_lines += 1
            current += 1
            maximum = max(maximum, current)
        else:
            current = 0
    return bullet_lines, content_lines, maximum


def paragraph_cjk_lengths(text: str) -> list[int]:
    lengths: list[int] = []
    buffer: list[str] = []
    for line in text.splitlines() + [""]:
        stripped = line.strip()
        if not stripped:
            if buffer:
                lengths.append(cjk_count("".join(buffer)))
                buffer = []
            continue
        if stripped.startswith("#") or stripped.startswith("|") or BULLET_RE.match(stripped):
            if buffer:
                lengths.append(cjk_count("".join(buffer)))
                buffer = []
            continue
        buffer.append(stripped)
    return lengths


def has_process_chain(text: str) -> bool:
    arrow_count = text.count("→") + text.count("->") + text.count("\\rightarrow")
    return arrow_count >= 3 or "mermaid" in text or "状态循环" in text or "过程链" in text


def math_without_nearby_explanation(text: str) -> bool:
    lines = text.splitlines()
    math_lines = {index for index, line in enumerate(lines) if "$$" in line or "\\[" in line or "\\]" in line}
    if not math_lines and not DISPLAY_MATH_RE.search(text):
        return False
    for index in sorted(math_lines):
        window = "\n".join(lines[max(0, index - 2) : min(len(lines), index + 3)])
        if cjk_count(window) >= 20 and any(token in window for token in ("其中", "表示", "含义", "条件", "所以", "因为", "题目")):
            return False
    return True


def lint_main_doc(text: str, *, path: Path | None = None) -> LintReport:
    report = LintReport()
    label = f"{path}: " if path else ""
    for phrase in OLD_CHECKLIST_SIGNALS:
        if phrase in text:
            report.add_error(f"{label}出现速查式主体信号 `{phrase}`；主干讲解不能退化成 checklist。")
    missing = [name for name, headings in MAIN_REQUIRED_HEADING_GROUPS if not has_any_heading(text, headings)]
    if missing:
        report.add_error(f"{label}主干讲解缺少必需结构：{', '.join(missing)}")
    template_count = fixed_template_sequence_count(text)
    if template_count >= 2:
        report.add_error(f"{label}固定五段模板重复出现 {template_count} 次；主干讲解应改成自然讲解结构。")
    elif template_count == 1:
        report.add_warning(f"{label}出现一次固定五段模板；确认它是自然讲解需要，而不是按检查项填空。")
    count = cjk_count(text)
    if count < 2000:
        report.add_error(f"{label}主干讲解中文字数约 {count}，过短；默认 S8 不能只给压缩卡片。")
    elif count < 2500:
        report.add_warning(f"{label}主干讲解中文字数约 {count}，偏短；确认不是速查卡。")
    paragraph_lengths = paragraph_cjk_lengths(text)
    if count >= 2000 and not any(length >= 80 for length in paragraph_lengths):
        report.add_error(f"{label}主干讲解缺少连续解释段；不要只用公式、表格或列表归档知识点。")
    bullets, content, max_run = bullet_stats(text)
    if content and bullets / content > 0.45:
        report.add_warning(f"{label}bullet 行占比 {bullets}/{content}，偏高；确认没有过度速查化，必要时补解释段、小例子或过渡句。")
    if max_run > 8:
        report.add_warning(f"{label}连续 bullet {max_run} 行；超过 8 行时建议改成解释段 + 小例子 + 自测。")
    long_paragraphs = [length for length in paragraph_lengths if length > 250]
    if long_paragraphs:
        report.add_warning(f"{label}存在 {len(long_paragraphs)} 个超过 250 中文字符的长段落。")
    if math_without_nearby_explanation(text):
        report.add_warning(f"{label}公式附近缺少符号含义、条件或题目触发信号解释。")
    if not has_process_chain(text):
        report.add_warning(f"{label}未发现明显因果链、状态循环、过程链或 Mermaid 增强。")
    if not has_any_heading(text, S10_ENTRY_HEADINGS):
        report.add_warning(f"{label}建议提供进入 S10 的问题入口，帮助主干讲解接到问答、做题或纠错。")
    return report


def lint_start_card(text: str, *, path: Path | None = None) -> LintReport:
    report = LintReport()
    label = f"{path}: " if path else ""
    for token in START_REQUIRED_TEXT:
        if token not in text[:500]:
            report.add_error(f"{label}S10启动卡开头必须声明它不替代主干讲解。")
            break
    if not any(token in text for token in ("参考答案", "判断标准", "答案要点")):
        report.add_error(f"{label}S10启动卡的最小自测必须附参考答案、判断标准或答案要点。")
    return report


def lint_grounding(text: str, *, path: Path | None = None) -> LintReport:
    report = LintReport()
    label = f"{path}: " if path else ""
    if not any(has_heading(text, heading) for heading in ("来源与边界", "范围待确认")):
        report.add_warning(f"{label}grounding 建议包含来源与边界或范围待确认。")
    if "S10" not in text or "probe" not in text:
        report.add_warning(f"{label}grounding 建议包含 S10 probe 种子。")
    return report


def lint_files(paths: list[Path], *, mode: str = "default") -> LintReport:
    report = LintReport()
    by_key: dict[str, set[str]] = {}
    role_paths: dict[str, dict[str, Path]] = {}
    texts: dict[Path, str] = {}
    for path in paths:
        role = classify(path)
        if not role:
            continue
        texts[path] = read_text(path)
        key = chapter_key(path)
        by_key.setdefault(key, set()).add(role)
        role_paths.setdefault(key, {})[role] = path
        if role == "main":
            report.extend(lint_main_doc(texts[path], path=path))
        elif role == "legacy_main":
            report.add_warning(f"{path}: 使用旧文件名 `主干重点`；新生成默认使用 `主干讲解`。")
            report.extend(lint_main_doc(texts[path], path=path))
        elif role == "start":
            report.extend(lint_start_card(texts[path], path=path))
        elif role == "legacy_starter":
            report.add_warning(f"{path}: 使用旧文件名 `入门讲解`；新生成默认使用 `S10启动卡`。")
        elif role == "grounding":
            report.extend(lint_grounding(texts[path], path=path))

    for key, roles in sorted(by_key.items()):
        has_main = bool(roles & {"main", "legacy_main"})
        if has_main:
            continue
        if mode == "grounding-only" and roles <= {"grounding"}:
            continue
        if mode == "quick-start-only" and roles <= {"start", "legacy_starter"}:
            continue
        if roles & {"grounding", "start"}:
            report.add_error(f"{key}: 默认 S8 产物不能只有 grounding 或 S10启动卡；必须先有主干讲解。")
        main_path = role_paths.get(key, {}).get("main") or role_paths.get(key, {}).get("legacy_main")
        start_path = role_paths.get(key, {}).get("start")
        if main_path and start_path and cjk_count(texts[start_path]) > cjk_count(texts[main_path]):
            report.add_warning(f"{start_path}: S10启动卡比主干讲解更长；确认它没有替代主干讲解。")
    return report


def lint_file(path: Path, *, mode: str = "default") -> None:
    report = lint_files([path], mode=mode)
    if report.errors:
        raise ChapterDocsLintError("\n".join(report.errors))


def lint_knowledge_root(root: Path, *, mode: str = "default") -> LintReport:
    paths = [path for path in sorted(root.glob("*.md")) if path.name not in {"README.md", "整体知识框架.md"}]
    return lint_files(paths, mode=mode)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", action="append", type=Path, default=[])
    parser.add_argument("--knowledge-root", type=Path)
    parser.add_argument("--mode", choices=("default", "grounding-only", "quick-start-only"), default="default")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.file and not args.knowledge_root:
        print("必须提供 --file 或 --knowledge-root", file=sys.stderr)
        return 3
    report = LintReport()
    try:
        if args.file:
            report.extend(lint_files(args.file, mode=args.mode))
        if args.knowledge_root:
            report.extend(lint_knowledge_root(args.knowledge_root, mode=args.mode))
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    for warning in report.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if report.errors:
        print("\n".join(report.errors), file=sys.stderr)
        return 2
    print("S8 章节文档 lint 通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
