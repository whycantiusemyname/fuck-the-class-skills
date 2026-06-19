#!/usr/bin/env python3
"""Validate Fuck The Class course artifacts with deterministic exit codes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

import analyze_frequency_trends as analyzer
import render_frequency_views as renderer
import course_profile


CONTROL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
KNOWN_LATEX_RE = re.compile(r"\$\$\$|\\left\$\$|\\right\$\$|(?<!\\)\b(?:frac|qquad|quad|left|right)\{")
BARE_MATH_RE = re.compile(r"\\(?:frac|dfrac|tfrac|sqrt|int|iint|iiint|sum|prod|lim|partial|nabla|infty|alpha|beta|gamma|theta)\b|[A-Za-z0-9)]\^[{A-Za-z0-9]")
WIKILINK_RE = re.compile(r"!?\[\[([^\]]+)\]\]")
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
DERIVED_MARKER = "> 派生文件，可重新生成，勿手改。"
SCOPES = {"s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9", "s10", "all"}
S7_ITEM_MARKER_RE = re.compile(r"^<!-- s7-item:([0-9a-fA-F]{64}):([^:]+):(.+?) -->$")
S7_CURRENT_TYPES = {"用户提问", "明确疑问", "被纠正的误解", "最终讲通解释"}
S7_LEGACY_TYPES = {"追问≥2轮"}
S7_ALLOWED_TYPES = S7_CURRENT_TYPES | S7_LEGACY_TYPES
S7_RANGE_LIST_RE = re.compile(r"^\d+-\d+(?:,\s*\d+-\d+)*$")
S10_EVENT_TYPES = {"attempt", "question", "explanation", "probe", "repair", "variant", "reflection", "state_update"}
S10_CONFIDENCE = {"low", "medium", "high"}
S10_JUDGEMENTS = {"对", "对但慢", "卡", "错", "空"}
S10_WRONG_CAUSES = {"概念错", "起手错", "计算错", "审题错", "没思路"}
S10_ORIGINS = {"s3", "s10", "manual", "import"}
S10_CREATED_BY = {"main_agent", "subagent", "user", "script"}
S10_OUTCOMES = {
    "not_tested",
    "observed",
    "repaired_independently",
    "repaired_with_hint",
    "needs_followup",
    "not_repaired",
    "deferred",
}
S10_S3_FORBIDDEN_FIELDS = {"diagnosis_hypothesis", "next_probe", "tutor_action", "hint_level"}
S5_HYPOTHESIS_MARKER_RE = re.compile(r"^<!-- s5-hypothesis:([^:]+):([^:]+):([0-9a-fA-F]{8}) -->$")
S4_CANDIDATE_FILE = "本轮练习候选.md"


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
        "s4": [course_root / "40_派生视图" / S4_CANDIDATE_FILE],
        "s5": [course_root / "40_派生视图" / "复盘报告.md", course_root / "30_我的数据" / "卡点清单.md"],
        "s6": [course_root / "40_派生视图" / "冲刺包.md", course_root / "40_派生视图" / "模拟卷.md"],
        "s7": [course_root / "30_我的数据" / "卡点清单.md"],
        "s8": [course_root / "20_知识"],
        "s9": [course_root / "10_题库"],
        "s10": [course_root / "40_派生视图" / "学生状态快照.md"],
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


def s1_artifact_issues(course_root: Path) -> list[str]:
    question_dir = course_root / "10_题库"
    question_files = sorted(question_dir.glob("*题面整理.md"))
    tag_library = question_dir / "_标签库.md"
    if not question_files and not tag_library.exists():
        return []
    issues: list[str] = []
    if not tag_library.exists():
        issues.append(f"缺少 S1 标签库：{tag_library}")
        return issues
    try:
        definitions = analyzer.parse_tag_library(tag_library)
        analyzer.parse_question_files(course_root, definitions)
    except analyzer.AnalysisBlocked as exc:
        issues.extend(str(error) for error in exc.errors)

    for path in question_files:
        lines = read_text(path).splitlines()
        first_heading_index = next(
            (index for index, line in enumerate(lines) if re.match(r"^#{1,6}\s+", line)),
            None,
        )
        paper_metadata = analyzer.parse_metadata_block(lines, first_heading_index) if first_heading_index is not None else None
        if not paper_metadata or not {"source", "paper_type", "academic_year"} <= paper_metadata.keys():
            issues.append(f"{path}: 新 S1 题库文件缺少文档级 source/paper_type/academic_year 元数据")

        matches = list(re.finditer(r"^###\s+(.+?)\s*$", read_text(path), flags=re.MULTILINE))
        text = read_text(path)
        for index, match in enumerate(matches):
            block_start = match.end()
            block_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            block_lines = text[block_start:block_end].splitlines()
            anchor = match.group(1).strip()
            metadata = analyzer.parse_metadata_block([f"### {anchor}", *block_lines], 0)
            if metadata is None:
                issues.append(f"{path}#{anchor}: 缺少题目隐藏标签")
                continue
            if metadata.get("question_type", "").startswith("真题整卷"):
                continue
            missing = {"chapter", "question_type", "source", "question_form", "ocr_status"} - metadata.keys()
            if missing:
                issues.append(f"{path}#{anchor}: 新 S1 题目缺少字段 {sorted(missing)}")
            if "paper_type" not in metadata and (not paper_metadata or "paper_type" not in paper_metadata):
                issues.append(f"{path}#{anchor}: 缺少 paper_type（题目级或文档级）")
            if "academic_year" not in metadata and (not paper_metadata or "academic_year" not in paper_metadata):
                issues.append(f"{path}#{anchor}: 缺少 academic_year（题目级或文档级；未知也要显式写 未知）")
    return issues


def normalize_s7_ranges(raw: str) -> str:
    return ",".join(part.strip() for part in raw.split(","))


def parse_s7_ranges(raw: str) -> list[tuple[int, int]] | None:
    if not S7_RANGE_LIST_RE.fullmatch(raw.strip()):
        return None
    ranges: list[tuple[int, int]] = []
    for part in raw.split(","):
        start_text, end_text = part.strip().split("-", 1)
        start, end = int(start_text), int(end_text)
        if start < 1 or end < start:
            return None
        ranges.append((start, end))
    return ranges


def s7_block_fields(block: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in block:
        match = re.match(
            r"^\s*(evidence_source|evidence_source_sha256|evidence_lines|quote_source|quote_source_sha256|quote_lines|quote_sha256|quote_scope_reason):\s*(.*?)\s*$",
            line,
        )
        if match:
            fields[match.group(1)] = match.group(2)
    return fields


def s7_item_marker_issues(course_root: Path) -> list[str]:
    blocker = course_root / "30_我的数据" / "卡点清单.md"
    if not blocker.exists():
        return []
    lines = read_text(blocker).splitlines()
    issues: list[str] = []
    markers: dict[tuple[str, str, str], int] = {}
    marker_indexes: list[int] = []

    for index, line in enumerate(lines):
        if line.startswith("<!-- s7-item:"):
            marker_indexes.append(index)
            match = S7_ITEM_MARKER_RE.fullmatch(line.strip())
            if not match:
                issues.append(f"{blocker}:{index + 1}: S7 item marker 格式错误")
                continue
            source_sha, item_type, evidence_lines = match.groups()
            item_type = item_type.strip()
            evidence_lines = normalize_s7_ranges(evidence_lines)
            key = (source_sha.lower(), item_type, evidence_lines)
            if key in markers:
                issues.append(f"{blocker}:{index + 1}: S7 item marker 重复，首次出现在第 {markers[key]} 行")
            else:
                markers[key] = index + 1
            if item_type not in S7_ALLOWED_TYPES:
                issues.append(f"{blocker}:{index + 1}: S7 item 类型不在允许集合中：{item_type}")
            if parse_s7_ranges(evidence_lines) is None:
                issues.append(f"{blocker}:{index + 1}: S7 item marker evidence_lines 格式错误")

    for position, index in enumerate(marker_indexes):
        marker_match = S7_ITEM_MARKER_RE.fullmatch(lines[index].strip())
        if not marker_match:
            continue
        marker_sha, marker_type, marker_ranges = marker_match.groups()
        next_index = marker_indexes[position + 1] if position + 1 < len(marker_indexes) else len(lines)
        block = lines[index + 1 : next_index]
        item_line = next((line for line in block if line.startswith("- 来源: S7学习对话提取")), "")
        if not item_line:
            issues.append(f"{blocker}:{index + 1}: S7 item marker 后缺少条目正文")
            continue
        item_type_match = re.search(r"类型:\s*([^｜]+)", item_line)
        if not item_type_match:
            issues.append(f"{blocker}:{index + 1}: S7 条目缺少类型")
            continue
        item_type = item_type_match.group(1).strip()
        if item_type != marker_type.strip():
            issues.append(f"{blocker}:{index + 1}: S7 marker 类型与条目类型不一致")

        fields = s7_block_fields(block)
        missing = {"evidence_source", "evidence_source_sha256", "evidence_lines"} - fields.keys()
        if missing:
            issues.append(f"{blocker}:{index + 1}: S7 新条目缺少证据字段 {sorted(missing)}")
            continue

        if fields["evidence_source_sha256"].lower() != marker_sha.lower():
            issues.append(f"{blocker}:{index + 1}: S7 marker SHA 与 evidence_source_sha256 不一致")
        if normalize_s7_ranges(fields["evidence_lines"]) != normalize_s7_ranges(marker_ranges):
            issues.append(f"{blocker}:{index + 1}: S7 marker evidence_lines 与字段不一致")

        source = resolve_vault_path(course_root.parent, fields["evidence_source"])
        if source is None:
            issues.append(f"{blocker}:{index + 1}: evidence_source 不存在")
            continue
        if sha256_bytes(source.read_bytes()) != fields["evidence_source_sha256"].lower():
            issues.append(f"{blocker}:{index + 1}: evidence_source_sha256 不匹配")
        source_lines = read_text(source).splitlines()
        ranges = parse_s7_ranges(fields["evidence_lines"])
        if ranges is None:
            issues.append(f"{blocker}:{index + 1}: evidence_lines 格式错误")
        else:
            for start, end in ranges:
                if end > len(source_lines):
                    issues.append(f"{blocker}:{index + 1}: evidence_lines 越界")
                    break

        if item_type == "最终讲通解释":
            quote_missing = {"quote_source", "quote_source_sha256", "quote_lines", "quote_sha256"} - fields.keys()
            if quote_missing:
                issues.append(f"{blocker}:{index + 1}: S7 最终讲通解释缺少引用字段 {sorted(quote_missing)}")
                continue
            if "原文摘录:" not in [line.strip() for line in block]:
                issues.append(f"{blocker}:{index + 1}: S7 最终讲通解释缺少原文摘录")
                continue
            quote_ranges = parse_s7_ranges(fields["quote_lines"])
            if quote_ranges is None or len(quote_ranges) != 1:
                issues.append(f"{blocker}:{index + 1}: quote_lines 格式错误")
            else:
                start, end = quote_ranges[0]
                if end - start + 1 > 25 and not fields.get("quote_scope_reason", "").strip():
                    issues.append(f"{blocker}:{index + 1}: 超过 25 行的最终讲通解释缺少 quote_scope_reason")
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
        block_start = 0
        for cursor in range(index - 1, -1, -1):
            if lines[cursor].startswith("<!-- s7-item:") or lines[cursor].startswith("- 来源: S7学习对话提取"):
                block_start = cursor
                break
            if lines[cursor].strip() == "原文摘录:":
                block_start = cursor + 1
                break
        for prior in lines[block_start:index]:
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


def s10_learning_event_issues(course_root: Path) -> list[str]:
    events = course_root / "30_我的数据" / "学习事件.jsonl"
    issues: list[str] = []
    if not events.exists():
        return [f"缺少 S10 学习事件文件：{events}"]
    event_ids: dict[str, int] = {}
    for line_number, line in enumerate(read_text(events).splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append(f"{events}:{line_number}: 不是合法 JSON：{exc.msg}")
            continue
        if not isinstance(item, dict):
            issues.append(f"{events}:{line_number}: JSONL 每行必须是对象")
            continue
        missing = {"event_id", "time", "event_type", "evidence", "origin"} - item.keys()
        if missing:
            issues.append(f"{events}:{line_number}: 缺少必填字段 {sorted(missing)}")
        event_id = item.get("event_id")
        if isinstance(event_id, str) and event_id:
            if event_id in event_ids:
                issues.append(f"{events}:{line_number}: event_id 重复，首次出现在第 {event_ids[event_id]} 行")
            else:
                event_ids[event_id] = line_number
        time_value = item.get("time")
        if isinstance(time_value, str):
            try:
                datetime.fromisoformat(time_value.replace("Z", "+00:00"))
            except ValueError:
                issues.append(f"{events}:{line_number}: time 不是 ISO 8601 时间：{time_value}")
        elif time_value is not None:
            issues.append(f"{events}:{line_number}: time 必须是字符串")
        event_type = item.get("event_type")
        if event_type not in S10_EVENT_TYPES:
            issues.append(f"{events}:{line_number}: event_type 不在允许集合中：{event_type}")
        origin = item.get("origin")
        if origin is not None and origin not in S10_ORIGINS:
            issues.append(f"{events}:{line_number}: origin 不在允许集合中：{origin}")
        created_by = item.get("created_by")
        if created_by is not None and created_by not in S10_CREATED_BY:
            issues.append(f"{events}:{line_number}: created_by 不在允许集合中：{created_by}")
        outcome = item.get("outcome")
        if outcome is not None and outcome not in S10_OUTCOMES:
            issues.append(f"{events}:{line_number}: outcome 不在允许集合中：{outcome}")
        if origin == "s3":
            if event_type != "attempt":
                issues.append(f"{events}:{line_number}: origin=s3 只能写 attempt 事件")
            forbidden = sorted(field for field in S10_S3_FORBIDDEN_FIELDS if field in item)
            if forbidden:
                issues.append(f"{events}:{line_number}: origin=s3 不得主动写 S10 字段 {forbidden}")
        confidence = item.get("confidence")
        if confidence is not None and confidence not in S10_CONFIDENCE:
            issues.append(f"{events}:{line_number}: confidence 不在允许集合中：{confidence}")
        judgement = item.get("judgement")
        if judgement is not None:
            if event_type != "attempt":
                issues.append(f"{events}:{line_number}: 非 attempt 事件不得写 judgement")
            if judgement not in S10_JUDGEMENTS:
                issues.append(f"{events}:{line_number}: judgement 不在允许集合中：{judgement}")
        wrong_cause = item.get("coarse_wrong_cause")
        if wrong_cause is not None:
            if event_type != "attempt":
                issues.append(f"{events}:{line_number}: 非 attempt 事件不得写 coarse_wrong_cause")
            if wrong_cause not in S10_WRONG_CAUSES:
                issues.append(f"{events}:{line_number}: coarse_wrong_cause 不在允许集合中：{wrong_cause}")
        if item.get("diagnosis_hypothesis") and (not item.get("confidence") or not item.get("next_probe")):
            issues.append(f"{events}:{line_number}: diagnosis_hypothesis 需要同时写 confidence 和 next_probe")
        source_refs = item.get("source_refs")
        if source_refs is not None and (
            not isinstance(source_refs, list) or any(not isinstance(ref, str) for ref in source_refs)
        ):
            issues.append(f"{events}:{line_number}: source_refs 必须是字符串数组")
        elif isinstance(source_refs, list):
            for ref in source_refs:
                if not re.fullmatch(r"!?\[\[[^\]]+\]\]", ref.strip()):
                    issues.append(f"{events}:{line_number}: source_refs 必须使用 wikilink：{ref}")
                    continue
                target, _ = split_wikilink(ref.strip().lstrip("!")[2:-2])
                if target.startswith("#"):
                    continue
                file_part, separator, heading = target.partition("#")
                resolved = resolve_vault_path(course_root.parent, file_part)
                if resolved is None:
                    issues.append(f"{events}:{line_number}: source_refs 断链 {ref}")
                elif separator and not heading_exists(resolved, heading):
                    issues.append(f"{events}:{line_number}: source_refs 缺少标题 {ref}")
        evidence = item.get("evidence")
        if evidence is not None and (not isinstance(evidence, str) or not evidence.strip()):
            issues.append(f"{events}:{line_number}: evidence 必须是非空字符串")
    return issues


def s5_marker_issues(course_root: Path) -> list[str]:
    blocker = course_root / "30_我的数据" / "卡点清单.md"
    if not blocker.exists():
        return []
    issues: list[str] = []
    seen: dict[tuple[str, str, str], int] = {}
    for line_number, line in enumerate(read_text(blocker).splitlines(), start=1):
        if not line.startswith("<!-- s5-hypothesis:"):
            continue
        match = S5_HYPOTHESIS_MARKER_RE.fullmatch(line.strip())
        if not match:
            issues.append(f"{blocker}:{line_number}: S5 hypothesis marker 格式错误")
            continue
        key = tuple(part.lower() for part in match.groups())
        if key in seen:
            issues.append(f"{blocker}:{line_number}: S5 hypothesis marker 重复，首次出现在第 {seen[key]} 行")
        else:
            seen[key] = line_number
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
        queue = course_root / "40_派生视图" / S4_CANDIDATE_FILE
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


def s8_manifest_issues(course_root: Path, *, strict_missing: bool) -> list[str]:
    manifests = sorted((course_root / "90_缓存" / "s8-digest").glob("*/digest.json"))
    knowledge_notes = [path for path in (course_root / "20_知识").glob("*.md") if path.name != "README.md"]
    if strict_missing and knowledge_notes and not manifests:
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
    if not files and scope != "s10":
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
    if scope in {"s1", "all"}:
        errors.extend(s1_artifact_issues(course_root))
    profile_path = course_profile.profile_path(course_root)
    if profile_path.exists():
        try:
            course_profile.parse_profile(profile_path)
        except course_profile.CourseProfileError as exc:
            errors.append(str(exc))
    if scope in {"s2", "all"}:
        errors.extend(s2_issues(course_root))
    if scope in {"s7", "all"}:
        errors.extend(s7_item_marker_issues(course_root))
        errors.extend(quote_evidence_issues(course_root))
    if scope in {"s5", "all"}:
        errors.extend(s5_marker_issues(course_root))
    if scope in {"s10", "all"}:
        errors.extend(s10_learning_event_issues(course_root))
    errors.extend(ocr_consumption_issues(course_root, scope))
    if scope in {"s6", "all"}:
        errors.extend(starter_provenance_issues(course_root))
    if scope in {"s8", "all"}:
        errors.extend(s8_manifest_issues(course_root, strict_missing=scope == "s8"))
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
