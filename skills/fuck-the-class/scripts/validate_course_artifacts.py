#!/usr/bin/env python3
"""Validate Fuck The Class course artifacts with deterministic exit codes."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path
from urllib.parse import unquote

import render_frequency_views as renderer


CONTROL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
KNOWN_LATEX_RE = re.compile(r"\$\$\$|\\left\$\$|\\right\$\$|(?<!\\)\b(?:frac|qquad|quad|left|right)\{")
BARE_MATH_RE = re.compile(r"\\(?:frac|dfrac|tfrac|sqrt|int|iint|iiint|sum|prod|lim|partial|nabla|infty|alpha|beta|gamma|theta)\b|[A-Za-z0-9)]\^[{A-Za-z0-9]")
WIKILINK_RE = re.compile(r"!?\[\[([^\]]+)\]\]")
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
DERIVED_MARKER = "> 派生文件，可重新生成，勿手改。"
SCOPES = {"s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9", "all"}


class ValidationConfigError(Exception):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def selected_markdown(course_root: Path, scope: str) -> list[Path]:
    mapping = {
        "s1": [course_root / "10_题库"],
        "s2": [course_root / "40_派生视图" / "考频矩阵.md", course_root / "40_派生视图" / "主题题表.md"],
        "s3": [course_root / "30_我的数据" / "做题记录.md"],
        "s4": [course_root / "40_派生视图" / "当日队列.md"],
        "s5": [course_root / "40_派生视图" / "复盘报告.md", course_root / "30_我的数据" / "卡点清单.md"],
        "s6": [course_root / "40_派生视图" / "冲刺包.md", course_root / "40_派生视图" / "模拟卷.md"],
        "s7": [course_root / "30_我的数据" / "卡点清单.md"],
        "s8": [course_root / "20_知识"],
        "s9": [course_root / "10_题库"],
        "all": [course_root / name for name in ("10_题库", "20_知识", "30_我的数据", "40_派生视图")],
    }
    paths: list[Path] = []
    for candidate in mapping[scope]:
        if candidate.is_dir():
            paths.extend(sorted(candidate.rglob("*.md")))
        elif candidate.exists():
            paths.append(candidate)
    return sorted(set(path.resolve() for path in paths))


def strip_code(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    return re.sub(r"`[^`\n]*`", "", text)


def latex_issues(path: Path, text: str) -> list[str]:
    issues: list[str] = []
    clean = strip_code(text)
    if KNOWN_LATEX_RE.search(clean):
        issues.append(f"{path}: 命中已知 LaTeX 损坏模式")
    left_count = len(re.findall(r"\\left(?![A-Za-z])", clean))
    right_count = len(re.findall(r"\\right(?![A-Za-z])", clean))
    if left_count != right_count:
        issues.append(f"{path}: \\left/\\right 数量不一致")
    display_count = len(re.findall(r"(?<!\\)\$\$", clean))
    if display_count % 2:
        issues.append(f"{path}: $$ 分隔符数量为奇数")
    without_display = re.sub(r"(?<!\\)\$\$.*?(?<!\\)\$\$", "", clean, flags=re.DOTALL)
    inline_count = len(re.findall(r"(?<!\\)(?<!\$)\$(?!\$)", without_display))
    if inline_count % 2:
        issues.append(f"{path}: $ 分隔符数量为奇数")
    return issues


def bare_math_warnings(path: Path, text: str) -> list[str]:
    clean = strip_code(text)
    clean = re.sub(r"(?<!\\)\$\$.*?(?<!\\)\$\$", "", clean, flags=re.DOTALL)
    clean = re.sub(r"(?<!\\)(?<!\$)\$.*?(?<!\\)\$(?!\$)", "", clean)
    if BARE_MATH_RE.search(clean):
        return [f"{path}: 疑似裸数学表达，请人工确认是否需要数学分隔符"]
    return []


def split_wikilink(raw: str) -> tuple[str, str | None]:
    parts = raw.replace(r"\|", "|").split("|", 1)
    target = parts[0].strip()
    alias = parts[1].strip() if len(parts) > 1 else None
    return target, alias


def resolve_vault_path(vault_root: Path, raw_path: str) -> Path | None:
    normalized = unquote(raw_path.strip().strip("<>")).replace("\\", "/")
    candidate = (vault_root / normalized).resolve()
    candidates = [candidate]
    if candidate.suffix == "":
        candidates.append(candidate.with_suffix(".md"))
    for path in candidates:
        if path.exists():
            return path
    if "/" not in normalized:
        matches = list(vault_root.rglob(normalized))
        if len(matches) == 1:
            return matches[0].resolve()
        if not Path(normalized).suffix:
            matches = list(vault_root.rglob(normalized + ".md"))
            if len(matches) == 1:
                return matches[0].resolve()
    return None


def heading_exists(path: Path, heading: str) -> bool:
    if path.suffix.lower() != ".md":
        return False
    headings = {match.group(1).strip() for match in HEADING_RE.finditer(read_text(path))}
    return unquote(heading).strip() in headings


def link_issues(course_root: Path, files: list[Path]) -> list[str]:
    vault_root = course_root.parent.resolve()
    issues: list[str] = []
    for source in files:
        text = read_text(source)
        for match in WIKILINK_RE.finditer(text):
            target, _ = split_wikilink(match.group(1))
            if not target:
                continue
            if target.startswith("#"):
                if not heading_exists(source, target[1:]):
                    issues.append(f"{source}: 缺少文内标题 #{target[1:]}")
                continue
            file_part, separator, heading = target.partition("#")
            normalized = file_part.replace("\\", "/").strip()
            if normalized.startswith(("../", "./", "/")) or re.match(r"^[A-Za-z]:/", normalized) or "/" not in normalized:
                issues.append(f"{source}: 跨文件链接不是 vault 根相对写法 [[{target}]]")
                continue
            resolved = resolve_vault_path(vault_root, file_part)
            if resolved is None:
                issues.append(f"{source}: 断链 [[{target}]]")
            elif separator and not heading_exists(resolved, heading):
                issues.append(f"{source}: 缺少标题 [[{target}]]")
        for match in MARKDOWN_LINK_RE.finditer(text):
            target = match.group(1).strip().split(maxsplit=1)[0].strip("<>")
            if not target or target.startswith(("http://", "https://", "mailto:", "data:", "#")):
                continue
            target = unquote(target)
            resolved = (source.parent / target).resolve()
            if not resolved.exists():
                issues.append(f"{source}: 断开的 Markdown 链接 ({target})")
    return issues


def derived_marker_issues(course_root: Path, files: list[Path]) -> list[str]:
    view_root = (course_root / "40_派生视图").resolve()
    issues: list[str] = []
    for path in files:
        try:
            path.relative_to(view_root)
        except ValueError:
            continue
        if read_text(path).splitlines()[:1] != [DERIVED_MARKER]:
            issues.append(f"{path}: 缺少派生文件标记")
    return issues


def quote_evidence_issues(course_root: Path) -> list[str]:
    blocker = course_root / "30_我的数据" / "卡点清单.md"
    if not blocker.exists():
        return []
    lines = read_text(blocker).splitlines()
    issues: list[str] = []
    for index, line in enumerate(lines):
        if line.strip() != "原文摘录:":
            continue
        metadata: dict[str, str] = {}
        for prior in lines[max(0, index - 8) : index]:
            match = re.match(r"^\s*(quote_source|quote_source_sha256|quote_lines|quote_sha256):\s*(.+?)\s*$", prior)
            if match:
                metadata[match.group(1)] = match.group(2)
        missing = {"quote_source", "quote_source_sha256", "quote_lines", "quote_sha256"} - metadata.keys()
        if missing:
            issues.append(f"{blocker}:{index + 1}: 原文摘录缺少证据字段 {sorted(missing)}")
            continue
        source = resolve_vault_path(course_root.parent, metadata["quote_source"])
        if source is None:
            issues.append(f"{blocker}:{index + 1}: quote_source 不存在")
            continue
        if sha256_bytes(source.read_bytes()) != metadata["quote_source_sha256"]:
            issues.append(f"{blocker}:{index + 1}: quote_source_sha256 不匹配")
        range_match = re.fullmatch(r"(\d+)-(\d+)", metadata["quote_lines"])
        if not range_match:
            issues.append(f"{blocker}:{index + 1}: quote_lines 格式错误")
            continue
        start, end = map(int, range_match.groups())
        source_lines = read_text(source).splitlines()
        if start < 1 or end < start or end > len(source_lines):
            issues.append(f"{blocker}:{index + 1}: quote_lines 越界")
            continue
        expected = "\n".join(source_lines[start - 1 : end])
        quote_lines: list[str] = []
        cursor = index + 1
        while cursor < len(lines):
            match = re.match(r"^\s*> ?(.*)$", lines[cursor])
            if not match:
                break
            quote_lines.append(match.group(1))
            cursor += 1
        actual = "\n".join(quote_lines)
        if actual != expected:
            issues.append(f"{blocker}:{index + 1}: 引用内容与源文件行范围不一致")
        if sha256_bytes(actual.encode("utf-8")) != metadata["quote_sha256"]:
            issues.append(f"{blocker}:{index + 1}: quote_sha256 不匹配")
    return issues


def question_statuses(course_root: Path) -> dict[str, tuple[str, Path, str]]:
    statuses: dict[str, tuple[str, Path, str]] = {}
    for path in sorted((course_root / "10_题库").glob("*题面整理.md")):
        text = read_text(path)
        matches = list(re.finditer(r"^###\s+(.+?)\s*$", text, flags=re.MULTILINE))
        for index, match in enumerate(matches):
            block = text[match.end() : matches[index + 1].start() if index + 1 < len(matches) else len(text)]
            status_match = re.search(r"^ocr_status:\s*(.+?)\s*$", block, flags=re.MULTILINE)
            status = status_match.group(1).strip() if status_match else "已做结构修复"
            statuses[match.group(1).strip()] = (status, path, block)
    return statuses


def linked_anchors(path: Path) -> set[str]:
    anchors: set[str] = set()
    if not path.exists():
        return anchors
    for match in WIKILINK_RE.finditer(read_text(path)):
        target, _ = split_wikilink(match.group(1))
        _, separator, anchor = target.partition("#")
        if separator and anchor:
            anchors.add(anchor)
    return anchors


def ocr_consumption_issues(course_root: Path, scope: str) -> list[str]:
    statuses = question_statuses(course_root)
    issues: list[str] = []
    if scope in {"s4", "all"}:
        queue = course_root / "40_派生视图" / "当日队列.md"
        for anchor in linked_anchors(queue):
            if statuses.get(anchor, (None, None, None))[0] == "待复核":
                issues.append(f"{queue}: 队列消费了待复核题 {anchor}")
    if scope in {"s9", "all"}:
        for anchor, (status, path, block) in statuses.items():
            if status == "待复核" and re.search(r"^> \[!note\]- 解答｜状态：", block, flags=re.MULTILINE):
                issues.append(f"{path}: 待复核题 {anchor} 含 S9 解答块")
    return issues


def starter_provenance_issues(course_root: Path) -> list[str]:
    cram = course_root / "40_派生视图" / "冲刺包.md"
    if not cram.exists():
        return []
    starters = renderer.parse_starters(course_root)
    records_path = course_root / "30_我的数据" / "做题记录.md"
    records = read_text(records_path) if records_path.exists() else ""
    issues: list[str] = []
    for line_number, line in enumerate(read_text(cram).splitlines(), start=1):
        if "起手：" not in line:
            continue
        content = line.split("起手：", 1)[1].strip()
        if content == "待 S9" or content.startswith("待 S9"):
            continue
        source_match = re.fullmatch(r"(.+?)｜来源：S9\s+(.+)", content)
        if source_match:
            starter, anchor = source_match.groups()
            if starters.get(anchor.strip()) != starter.strip():
                issues.append(f"{cram}:{line_number}: S9 起手来源与解答块不一致")
            continue
        record_match = re.fullmatch(r"(.+?)｜来源：用户确认记录\s+(\d{4}-\d{2}-\d{2})", content)
        if record_match:
            if record_match.group(2) not in records:
                issues.append(f"{cram}:{line_number}: 用户确认记录日期不存在")
            continue
        issues.append(f"{cram}:{line_number}: 起手缺少允许的来源")
    return issues


def s8_manifest_issues(course_root: Path) -> list[str]:
    manifests = sorted((course_root / "90_缓存" / "s8-digest").glob("*/digest.json"))
    knowledge_notes = [path for path in (course_root / "20_知识").glob("*.md") if path.name != "README.md"]
    if knowledge_notes and not manifests:
        return ["20_知识 存在章节产物但没有 S8 digest manifest"]
    import s8_digest_gate

    issues: list[str] = []
    for manifest in manifests:
        try:
            s8_digest_gate.verify(manifest)
        except s8_digest_gate.DigestError as exc:
            issues.append(str(exc))
    return issues


def s2_issues(course_root: Path) -> list[str]:
    analysis = course_root / "90_缓存" / "s2-frequency-analysis.json"
    if not analysis.exists():
        return [f"缺少 S2 分析缓存：{analysis}"]
    try:
        outputs = renderer.build_outputs(course_root, analysis)
    except renderer.RenderError as exc:
        return [str(exc)]
    issues: list[str] = []
    for path, expected in outputs.items():
        if not path.exists():
            issues.append(f"缺少派生文件：{path}")
        elif read_text(path) != expected:
            issues.append(f"派生文件与 S2 JSON 不一致：{path}")
    return issues


def validate(course_root: Path, scope: str) -> tuple[list[str], list[str], dict[str, int]]:
    if not course_root.is_dir():
        raise ValidationConfigError(f"课程目录不存在：{course_root}")
    files = selected_markdown(course_root, scope)
    if not files:
        raise ValidationConfigError(f"scope={scope} 没有找到可校验 Markdown")
    control: list[str] = []
    latex: list[str] = []
    bare_math: list[str] = []
    for path in files:
        text = read_text(path)
        if CONTROL_RE.search(text):
            control.append(f"{path}: 含控制字符")
        latex.extend(latex_issues(path, text))
        bare_math.extend(bare_math_warnings(path, text))
    links = link_issues(course_root, files)
    errors = [*control, *latex, *links, *derived_marker_issues(course_root, files)]
    if scope in {"s2", "all"}:
        errors.extend(s2_issues(course_root))
    if scope in {"s7", "all"}:
        errors.extend(quote_evidence_issues(course_root))
    errors.extend(ocr_consumption_issues(course_root, scope))
    if scope in {"s6", "all"}:
        errors.extend(starter_provenance_issues(course_root))
    if scope in {"s8", "all"}:
        errors.extend(s8_manifest_issues(course_root))
    counts = {"control": len(control), "latex": len(latex), "links": len(links)}
    warnings = bare_math
    return errors, warnings, counts


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--course-root", required=True, type=Path)
    parser.add_argument("--scope", required=True, choices=sorted(SCOPES))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        errors, warnings, counts = validate(args.course_root.resolve(), args.scope)
    except ValidationConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        print(f"自检：控制字符 {counts['control']}，LaTeX 异常 {counts['latex']}，断链 {counts['links']}")
        return 2
    print("自检：控制字符 0，LaTeX 异常 0，断链 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
