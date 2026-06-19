#!/usr/bin/env python3
"""Deterministic frequency and trend analysis for Fuck The Class S2."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "2.0"
QUESTION_FORMS = {
    "选择题",
    "填空题",
    "计算题",
    "证明题",
    "应用题",
    "简答题",
    "综合题",
    "未判定",
}
LONG_FORMS = {"计算题", "证明题", "应用题", "综合题"}
FORM_PATTERNS = (
    (re.compile(r"-选"), "选择题"),
    (re.compile(r"-填"), "填空题"),
    (re.compile(r"-算"), "计算题"),
    (re.compile(r"-证"), "证明题"),
    (re.compile(r"-应"), "应用题"),
)
TREND_PRIORITY = {
    "首次成势": 1,
    "沉寂后回归": 2,
    "新近升温": 3,
    "明显降温": 4,
    "稳定核心": 5,
    "周期波动": 6,
    "平稳观察": 7,
    "样本不足": 8,
}
OCR_STATUSES = {"待复核", "已做结构修复", "已对照 PDF 复核"}
WARMING_TRENDS = {"首次成势", "沉寂后回归", "新近升温"}


class AnalysisBlocked(Exception):
    def __init__(self, errors: list[str], warnings: list[str] | None = None):
        super().__init__("; ".join(errors))
        self.errors = errors
        self.warnings = warnings or []


@dataclass(frozen=True)
class TagDefinition:
    chapter: str
    theme: str
    tag: str
    expected_count: int


@dataclass(frozen=True)
class Question:
    file: str
    anchor: str
    chapter: str
    tag: str
    theme: str
    source: str
    paper_type: str
    academic_year: str | None
    year_start: int | None
    score: float | None
    question_form: str
    form_source: str
    ocr_status: str
    ocr_status_source: str

    @property
    def paper_key(self) -> str:
        return f"{self.file}|{self.source}"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def round_half_up(value: float | int | Decimal, digits: int = 0) -> float | int:
    quantum = Decimal("1").scaleb(-digits)
    rounded = Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP)
    return int(rounded) if digits == 0 else float(rounded)


def parse_metadata_block(lines: list[str], heading_index: int) -> dict[str, str] | None:
    """Read only a metadata block immediately adjacent to a heading."""
    index = heading_index + 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines) or lines[index].strip() != "%%":
        return None
    index += 1
    metadata: dict[str, str] = {}
    while index < len(lines) and lines[index].strip() != "%%":
        match = re.match(r"^([A-Za-z_]+):\s*(.*)$", lines[index])
        if match:
            metadata[match.group(1)] = match.group(2).strip()
        index += 1
    if index >= len(lines):
        return None
    return metadata


def parse_tag_library(path: Path) -> dict[str, TagDefinition]:
    definitions: dict[str, TagDefinition] = {}
    errors: list[str] = []
    row_pattern = re.compile(
        r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*`([^`]+)`\s*\|\s*(\d+)\s*\|\s*$"
    )
    for line_number, line in enumerate(read_text(path).splitlines(), start=1):
        match = row_pattern.match(line)
        if not match:
            continue
        chapter, theme, tag, count = (part.strip() for part in match.groups())
        if tag in definitions:
            errors.append(f"标签库重复标签：{tag}（第 {line_number} 行）")
            continue
        if not theme or theme in {"能力主题", "---"}:
            errors.append(f"标签缺少能力主题：{tag}")
            continue
        definitions[tag] = TagDefinition(chapter, theme, tag, int(count))
    if not definitions:
        errors.append("标签库没有找到四列表格：章节｜能力主题｜标准知识点标签｜题数")
    if errors:
        raise AnalysisBlocked(errors)
    return definitions


def infer_paper_type(source: str) -> str:
    if "期中" in source:
        return "期中"
    if "期末" in source or "缺卷头" in source:
        return "期末"
    return "其他"


def normalize_academic_year(value: str | None, source: str) -> tuple[str | None, int | None]:
    candidate = value or source
    match = re.search(r"(?<!\d)(\d{4})-(\d{4})(?!\d)", candidate)
    if not match:
        return None, None
    start, end = int(match.group(1)), int(match.group(2))
    if end != start + 1:
        return None, None
    return f"{start:04d}-{end:04d}", start


def infer_question_form(anchor: str, explicit: str | None) -> tuple[str, str]:
    if explicit:
        if explicit not in QUESTION_FORMS:
            raise ValueError(f"非法 question_form：{explicit}")
        return explicit, "explicit"
    for pattern, question_form in FORM_PATTERNS:
        if pattern.search(anchor):
            return question_form, "anchor"
    return "未判定", "unknown"


def parse_score(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    if not match:
        return None
    score = float(match.group(0))
    return score if score > 0 else None


def parse_question_files(course_root: Path, definitions: dict[str, TagDefinition]) -> tuple[list[Question], list[str]]:
    question_dir = course_root / "10_题库"
    errors: list[str] = []
    warnings: list[str] = []
    questions: list[Question] = []
    seen_anchors: dict[str, str] = {}
    files = sorted(question_dir.glob("*题面整理.md"), key=lambda path: path.name)
    if not files:
        raise AnalysisBlocked([f"没有找到题库文件：{question_dir / '*题面整理.md'}"])

    for path in files:
        lines = read_text(path).splitlines()
        paper_metadata: dict[str, str] = {}
        paper_heading_index: int | None = None
        first_heading_index = next(
            (index for index, line in enumerate(lines) if re.match(r"^#{1,6}\s+", line)),
            None,
        )
        if first_heading_index is not None:
            candidate = parse_metadata_block(lines, first_heading_index) or {}
            if {"paper_type", "academic_year", "source"} & candidate.keys():
                paper_metadata = candidate
                paper_heading_index = first_heading_index

        for index, line in enumerate(lines):
            if index == paper_heading_index:
                continue
            match = re.match(r"^###\s+(.+?)\s*$", line)
            if not match:
                continue
            anchor = match.group(1).strip()
            metadata = parse_metadata_block(lines, index)
            if metadata is None:
                continue
            tag = metadata.get("question_type", "").strip()
            chapter = metadata.get("chapter", "").strip()
            source = metadata.get("source", paper_metadata.get("source", "")).strip()
            if not tag or not chapter or not source:
                errors.append(f"{path.name}#{anchor} 缺少 chapter/question_type/source")
                continue
            definition = definitions.get(tag)
            if definition is None:
                errors.append(f"{path.name}#{anchor} 使用未知标签：{tag}")
                continue
            if anchor in seen_anchors:
                errors.append(f"重复锚点：{anchor}（{seen_anchors[anchor]}；{path.name}）")
                continue
            seen_anchors[anchor] = path.name

            paper_type = metadata.get("paper_type", paper_metadata.get("paper_type", "")).strip()
            paper_type = paper_type or infer_paper_type(source)
            academic_value = metadata.get("academic_year", paper_metadata.get("academic_year"))
            academic_year, year_start = normalize_academic_year(academic_value, source)
            try:
                question_form, form_source = infer_question_form(anchor, metadata.get("question_form"))
            except ValueError as exc:
                errors.append(f"{path.name}#{anchor} {exc}")
                continue
            explicit_ocr = metadata.get("ocr_status", "").strip()
            if explicit_ocr and explicit_ocr not in OCR_STATUSES:
                errors.append(f"{path.name}#{anchor} 非法 ocr_status：{explicit_ocr}")
                continue
            ocr_status = explicit_ocr or "已做结构修复"
            questions.append(
                Question(
                    file=path.stem,
                    anchor=anchor,
                    chapter=chapter,
                    tag=tag,
                    theme=definition.theme,
                    source=source,
                    paper_type=paper_type,
                    academic_year=academic_year,
                    year_start=year_start,
                    score=parse_score(metadata.get("score")),
                    question_form=question_form,
                    form_source=form_source,
                    ocr_status=ocr_status,
                    ocr_status_source="explicit" if explicit_ocr else "legacy_default",
                )
            )

    actual_counts = Counter(question.tag for question in questions)
    for tag, definition in definitions.items():
        actual = actual_counts.get(tag, 0)
        if actual != definition.expected_count:
            errors.append(f"标签计数不一致：{tag}，标签库 {definition.expected_count}，题库 {actual}")
    if errors:
        raise AnalysisBlocked(errors, warnings)
    return questions, warnings


def input_files(course_root: Path) -> list[Path]:
    question_dir = course_root / "10_题库"
    return [question_dir / "_标签库.md", *sorted(question_dir.glob("*题面整理.md"), key=lambda path: path.name)]


def calculate_input_fingerprint(course_root: Path) -> tuple[str, list[dict[str, str]]]:
    digest = hashlib.sha256()
    records: list[dict[str, str]] = []
    for path in input_files(course_root):
        data = path.read_bytes()
        relative = path.relative_to(course_root).as_posix()
        file_hash = hashlib.sha256(data).hexdigest()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
        records.append({"path": relative, "sha256": file_hash})
    return digest.hexdigest(), records


def group_papers(questions: Iterable[Question]) -> dict[str, list[Question]]:
    grouped: dict[str, list[Question]] = defaultdict(list)
    for question in questions:
        grouped[question.paper_key].append(question)
    return dict(grouped)


def coverage(entity_questions: list[Question], valid_years: list[int]) -> tuple[int, int, float | None]:
    present_years = {question.year_start for question in entity_questions if question.year_start in valid_years}
    numerator, denominator = len(present_years), len(valid_years)
    return numerator, denominator, round(numerator / denominator, 4) if denominator else None


def average_questions_per_paper(entity_questions: list[Question], period_papers: set[str]) -> float | None:
    if not period_papers:
        return None
    count = sum(1 for question in entity_questions if question.paper_key in period_papers)
    return round(count / len(period_papers), 4)


def equal_weight_form_distribution(entity_questions: list[Question], period_papers: set[str]) -> dict[str, float]:
    per_paper: list[Counter[str]] = []
    for paper_key in sorted(period_papers):
        forms = [
            question.question_form
            for question in entity_questions
            if question.paper_key == paper_key and question.question_form != "未判定"
        ]
        if forms:
            per_paper.append(Counter(forms))
    if not per_paper:
        return {}
    totals: Counter[str] = Counter()
    for counts in per_paper:
        denominator = sum(counts.values())
        for form, count in counts.items():
            totals[form] += count / denominator
    return {form: round(totals[form] / len(per_paper), 4) for form in sorted(totals)}


def long_ratio(form_distribution: dict[str, float]) -> float | None:
    if not form_distribution:
        return None
    return round(sum(value for form, value in form_distribution.items() if form in LONG_FORMS), 4)


def score_median(entity_questions: list[Question], period_papers: set[str]) -> tuple[int, float | None]:
    values = [question.score for question in entity_questions if question.paper_key in period_papers and question.score]
    return len(values), round(float(statistics.median(values)), 4) if values else None


def consecutive_counts(series: list[dict[str, Any]]) -> tuple[int, int]:
    if not series:
        return 0, 0
    target = bool(series[-1]["present"])
    count = 0
    for row in reversed(series):
        if bool(row["present"]) != target:
            break
        count += 1
    return (count, 0) if target else (0, count)


def transition_count(series: list[dict[str, Any]]) -> int:
    return sum(
        1
        for left, right in zip(series, series[1:])
        if bool(left["present"]) != bool(right["present"])
    )


def has_return_pattern(series: list[dict[str, Any]]) -> bool:
    present_run, _ = consecutive_counts(series)
    if present_run < 2:
        return False
    before = series[:-present_run]
    absent_run = 0
    for row in reversed(before):
        if row["present"]:
            break
        absent_run += 1
    earlier = before[:-absent_run] if absent_run else before
    return absent_run >= 2 and any(row["present"] for row in earlier)


def classify_primary_trend(
    historical: dict[str, Any], recent: dict[str, Any], full_series: list[dict[str, Any]]
) -> str:
    if historical["year_count"] < 3 or recent["year_count"] < 3:
        return "样本不足"
    latest_present = bool(full_series and full_series[-1]["present"])
    present_run, absent_run = consecutive_counts(full_series)
    hist_rate = historical["coverage_rate"] or 0.0
    recent_rate = recent["coverage_rate"] or 0.0
    delta = recent_rate - hist_rate
    if hist_rate == 0 and recent["coverage_numerator"] >= 2 and latest_present:
        return "首次成势"
    if has_return_pattern(full_series):
        return "沉寂后回归"
    if recent_rate >= 0.5 and delta >= 0.3 and latest_present:
        return "新近升温"
    if hist_rate >= 0.5 and recent_rate <= 0.25 and absent_run >= 2:
        return "明显降温"
    if hist_rate >= 0.6 and recent_rate >= 0.75 and latest_present:
        return "稳定核心"
    if transition_count(full_series) >= 3:
        return "周期波动"
    return "平稳观察"


def classify_size_shift(historical: dict[str, Any], recent: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    historical_long = historical.get("long_ratio")
    recent_long = recent.get("long_ratio")
    if (
        historical["known_form_count"] >= 3
        and recent["known_form_count"] >= 3
        and historical_long is not None
        and recent_long is not None
    ):
        delta = recent_long - historical_long
        if recent_long >= 0.6 and delta >= 0.35:
            labels.append("大题化")
        elif historical_long >= 0.6 and delta <= -0.35:
            labels.append("小题化")
    if historical["known_score_count"] >= 3 and recent["known_score_count"] >= 3:
        score_delta = recent["median_score"] - historical["median_score"]
        if score_delta >= 4 and "大题化" not in labels:
            labels.append("大题化")
        elif score_delta <= -4 and "小题化" not in labels:
            labels.append("小题化")
    return labels


def classify_importance_role(recent: dict[str, Any], primary_trend: str) -> str:
    recent_rate = recent.get("coverage_rate") or 0.0
    recent_median = recent.get("median_score")
    if recent_rate == 0:
        return "该卷型未覆盖"
    if recent_rate >= 0.75 and recent_median is not None and recent_median >= 8:
        return "高分杠杆"
    if recent_rate >= 0.75:
        return "高频主力"
    if recent_rate >= 0.5:
        return "中频主干"
    if primary_trend in WARMING_TRENDS:
        return "低频风险"
    return "低频观察"


def equal_weight_tag_distribution(entity_questions: list[Question], period_papers: set[str]) -> dict[str, float]:
    per_paper: list[Counter[str]] = []
    for paper_key in sorted(period_papers):
        tags = [question.tag for question in entity_questions if question.paper_key == paper_key]
        if tags:
            per_paper.append(Counter(tags))
    if not per_paper:
        return {}
    totals: Counter[str] = Counter()
    for counts in per_paper:
        denominator = sum(counts.values())
        for tag, count in counts.items():
            totals[tag] += count / denominator
    return {tag: round(totals[tag] / len(per_paper), 4) for tag in sorted(totals)}


def dominant_tag(distribution: dict[str, float]) -> tuple[str | None, float | None]:
    if not distribution:
        return None, None
    tag, share = sorted(distribution.items(), key=lambda item: (-item[1], item[0]))[0]
    return tag, share


def representative_payload(question: Question) -> dict[str, Any]:
    return {
        "file": question.file,
        "anchor": question.anchor,
        "source": question.source,
        "academic_year": question.academic_year,
        "score": question.score,
        "question_form": question.question_form,
        "tag": question.tag,
    }


def choose_representatives(questions: list[Question], recent_start: int) -> dict[str, list[dict[str, Any]]]:
    known_year = [question for question in questions if question.year_start is not None]
    historical = [question for question in known_year if question.year_start < recent_start]
    recent = [question for question in known_year if question.year_start >= recent_start]
    historical.sort(key=lambda q: (-(q.year_start or 0), -(q.score or 0), q.anchor))
    recent.sort(key=lambda q: (-(q.year_start or 0), -(q.score or 0), q.anchor))
    selected_recent: list[Question] = []
    seen_tags: set[str] = set()
    for question in recent:
        if question.tag not in seen_tags:
            selected_recent.append(question)
            seen_tags.add(question.tag)
        if len(selected_recent) == 2:
            break
    for question in recent:
        if len(selected_recent) == 2:
            break
        if question not in selected_recent:
            selected_recent.append(question)
    return {
        "historical": [representative_payload(question) for question in historical[:1]],
        "recent": [representative_payload(question) for question in selected_recent],
    }


def period_metrics(
    entity_questions: list[Question], years: list[int], papers_by_year: dict[int, set[str]]
) -> dict[str, Any]:
    period_papers = set().union(*(papers_by_year[year] for year in years)) if years else set()
    numerator, denominator, rate = coverage(entity_questions, years)
    forms = equal_weight_form_distribution(entity_questions, period_papers)
    known_form_count = sum(
        1
        for question in entity_questions
        if question.paper_key in period_papers and question.question_form != "未判定"
    )
    known_score_count, median_value = score_median(entity_questions, period_papers)
    known_score_total = round(sum(
        question.score or 0
        for question in entity_questions
        if question.paper_key in period_papers
    ), 4)
    known_score_per_paper = round(known_score_total / len(period_papers), 4) if period_papers else None
    return {
        "years": [f"{year:04d}-{year + 1:04d}" for year in years],
        "year_count": len(years),
        "paper_count": len(period_papers),
        "coverage_numerator": numerator,
        "coverage_denominator": denominator,
        "coverage_rate": rate,
        "year_coverage_numerator": numerator,
        "year_coverage_denominator": denominator,
        "year_coverage_rate": rate,
        "average_questions_per_paper": average_questions_per_paper(entity_questions, period_papers),
        "known_form_count": known_form_count,
        "form_distribution": forms,
        "long_ratio": long_ratio(forms),
        "known_score_count": known_score_count,
        "known_score_total": known_score_total,
        "known_score_per_paper": known_score_per_paper,
        "median_score": median_value,
    }


def build_exam_profile(
    entity_questions: list[Question], all_questions: list[Question], paper_type: str, recent_span: int, is_theme: bool
) -> dict[str, Any]:
    type_questions = [question for question in all_questions if question.paper_type == paper_type]
    papers_by_year: dict[int, set[str]] = defaultdict(set)
    for question in type_questions:
        if question.year_start is not None:
            papers_by_year[question.year_start].add(question.paper_key)
    valid_years = sorted(papers_by_year)
    latest_year = max(valid_years) if valid_years else None
    recent_start = latest_year - recent_span + 1 if latest_year is not None else 0
    historical_years = [year for year in valid_years if year < recent_start]
    recent_years = [year for year in valid_years if year >= recent_start]
    scoped = [question for question in entity_questions if question.paper_type == paper_type]
    entity_years = {question.year_start for question in scoped if question.year_start is not None}
    full_series = [
        {
            "academic_year": f"{year:04d}-{year + 1:04d}",
            "present": year in entity_years,
            "paper_count": len(papers_by_year[year]),
            "question_count": sum(1 for question in scoped if question.year_start == year),
        }
        for year in valid_years
    ]
    historical = period_metrics(scoped, historical_years, papers_by_year)
    recent = period_metrics(scoped, recent_years, papers_by_year)
    primary = classify_primary_trend(historical, recent, full_series)
    secondary = classify_size_shift(historical, recent)

    historical_papers = set().union(*(papers_by_year[year] for year in historical_years)) if historical_years else set()
    recent_papers = set().union(*(papers_by_year[year] for year in recent_years)) if recent_years else set()
    tag_change: dict[str, Any] | None = None
    if is_theme:
        historical_tags = equal_weight_tag_distribution(scoped, historical_papers)
        recent_tags = equal_weight_tag_distribution(scoped, recent_papers)
        old_tag, old_share = dominant_tag(historical_tags)
        new_tag, new_share = dominant_tag(recent_tags)
        recent_tag_years = len({
            question.year_start
            for question in scoped
            if question.year_start in recent_years and question.tag == new_tag
        }) if new_tag else 0
        historical_instances = sum(1 for question in scoped if question.paper_key in historical_papers)
        recent_instances = sum(1 for question in scoped if question.paper_key in recent_papers)
        old_new_share = historical_tags.get(new_tag, 0.0) if new_tag else 0.0
        migrated = (
            historical_instances >= 5
            and recent_instances >= 3
            and old_tag is not None
            and new_tag is not None
            and old_tag != new_tag
            and (new_share or 0.0) >= 0.4
            and (new_share or 0.0) - old_new_share >= 0.25
            and recent_tag_years >= 2
        )
        if migrated:
            secondary.append("考法迁移")
        tag_change = {
            "historical_distribution": historical_tags,
            "recent_distribution": recent_tags,
            "historical_dominant_tag": old_tag,
            "historical_dominant_share": old_share,
            "recent_dominant_tag": new_tag,
            "recent_dominant_share": new_share,
            "recent_dominant_tag_years": recent_tag_years,
            "migrated": migrated,
        }

    present_run, absent_run = consecutive_counts(full_series)
    known_years = sorted({question.year_start for question in scoped if question.year_start is not None})
    importance_role = classify_importance_role(recent, primary)
    return {
        "paper_type": paper_type,
        "recent_start_year": f"{recent_start:04d}-{recent_start + 1:04d}" if latest_year is not None else None,
        "latest_year": f"{latest_year:04d}-{latest_year + 1:04d}" if latest_year is not None else None,
        "historical": historical,
        "recent": recent,
        "coverage_delta": round((recent["coverage_rate"] or 0.0) - (historical["coverage_rate"] or 0.0), 4),
        "first_seen_year": f"{known_years[0]:04d}-{known_years[0] + 1:04d}" if known_years else None,
        "last_seen_year": f"{known_years[-1]:04d}-{known_years[-1] + 1:04d}" if known_years else None,
        "current_consecutive_present": present_run,
        "current_consecutive_absent": absent_run,
        "transition_count": transition_count(full_series),
        "primary_trend": primary,
        "trend_priority": TREND_PRIORITY[primary],
        "importance_role": importance_role,
        "secondary_trends": secondary,
        "tag_change": tag_change,
        "representatives": choose_representatives(scoped, recent_start) if latest_year is not None else {"historical": [], "recent": []},
        "year_series": full_series,
    }


def build_analysis(course_root: Path, recent_span: int) -> dict[str, Any]:
    tag_library = course_root / "10_题库" / "_标签库.md"
    definitions = parse_tag_library(tag_library)
    questions, warnings = parse_question_files(course_root, definitions)
    fingerprint, fingerprint_files = calculate_input_fingerprint(course_root)
    paper_groups = group_papers(questions)
    paper_types = sorted({question.paper_type for question in questions}, key=lambda value: (value not in {"期中", "期末"}, value))

    themes: list[dict[str, Any]] = []
    for theme in sorted({definition.theme for definition in definitions.values()}):
        scoped = [question for question in questions if question.theme == theme]
        themes.append({
            "name": theme,
            "question_count": len(scoped),
            "known_score_total": round(sum(question.score or 0 for question in scoped), 4),
            "exam_profiles": {
                paper_type: build_exam_profile(scoped, questions, paper_type, recent_span, True)
                for paper_type in paper_types
            },
        })

    tags: list[dict[str, Any]] = []
    for tag in sorted(definitions):
        scoped = [question for question in questions if question.tag == tag]
        definition = definitions[tag]
        tags.append({
            "name": tag,
            "chapter": definition.chapter,
            "theme": definition.theme,
            "question_count": len(scoped),
            "known_score_total": round(sum(question.score or 0 for question in scoped), 4),
            "exam_profiles": {
                paper_type: build_exam_profile(scoped, questions, paper_type, recent_span, False)
                for paper_type in paper_types
            },
        })

    unknown_year_papers = sorted({question.paper_key for question in questions if question.year_start is None})
    form_sources = Counter(question.form_source for question in questions)
    ocr_sources = Counter(question.ocr_status_source for question in questions)
    ocr_statuses = Counter(question.ocr_status for question in questions)
    if unknown_year_papers:
        warnings.append(f"{len(unknown_year_papers)} 份试卷缺少可用学年，只参加总频次")
    if form_sources.get("unknown", 0):
        warnings.append(f"{form_sources['unknown']} 道题的 question_form 未判定")

    year_series: list[dict[str, Any]] = []
    for paper_type in paper_types:
        years = sorted({question.year_start for question in questions if question.paper_type == paper_type and question.year_start is not None})
        for year in years:
            year_questions = [question for question in questions if question.paper_type == paper_type and question.year_start == year]
            year_series.append({
                "paper_type": paper_type,
                "academic_year": f"{year:04d}-{year + 1:04d}",
                "paper_count": len({question.paper_key for question in year_questions}),
                "question_count": len(year_questions),
                "theme_counts": dict(sorted(Counter(question.theme for question in year_questions).items())),
                "tag_counts": dict(sorted(Counter(question.tag for question in year_questions).items())),
            })

    paper_series: list[dict[str, Any]] = []
    for paper_key, paper_questions in sorted(paper_groups.items()):
        first = paper_questions[0]
        paper_series.append({
            "paper_key": paper_key,
            "file": first.file,
            "source": first.source,
            "paper_type": first.paper_type,
            "academic_year": first.academic_year,
            "question_count": len(paper_questions),
            "theme_counts": dict(sorted(Counter(question.theme for question in paper_questions).items())),
            "tag_counts": dict(sorted(Counter(question.tag for question in paper_questions).items())),
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "input_fingerprint": fingerprint,
        "input_files": fingerprint_files,
        "parameters": {"recent_year_span": recent_span},
        "scope": {
            "question_count": len(questions),
            "unique_anchor_count": len({question.anchor for question in questions}),
            "paper_count": len(paper_groups),
            "tag_count": len(definitions),
            "theme_count": len({definition.theme for definition in definitions.values()}),
            "paper_types": {
                paper_type: len({question.paper_key for question in questions if question.paper_type == paper_type})
                for paper_type in paper_types
            },
        },
        "quality": {
            "question_form_explicit": form_sources.get("explicit", 0),
            "question_form_inferred": form_sources.get("anchor", 0),
            "question_form_unknown": form_sources.get("unknown", 0),
            "ocr_status_explicit": ocr_sources.get("explicit", 0),
            "ocr_status_legacy_default": ocr_sources.get("legacy_default", 0),
            "ocr_status_counts": dict(sorted(ocr_statuses.items())),
            "unknown_year_paper_count": len(unknown_year_papers),
            "unknown_year_papers": unknown_year_papers,
            "tag_count_matches": True,
            "theme_mapping_complete": True,
        },
        "themes": themes,
        "tags": tags,
        "year_series": year_series,
        "paper_series": paper_series,
        "warnings": warnings,
    }


def write_json(path: Path | None, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if path is None:
        sys.stdout.write(text)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)


def blocked_payload(errors: list[str], warnings: list[str], recent_span: int) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "blocked",
        "input_fingerprint": None,
        "parameters": {"recent_year_span": recent_span},
        "errors": errors,
        "warnings": warnings,
    }


def verify_existing(course_root: Path, analysis_path: Path) -> int:
    payload = json.loads(read_text(analysis_path))
    if payload.get("status") != "complete":
        print("analysis status is not complete", file=sys.stderr)
        return 3
    if payload.get("schema_version") != SCHEMA_VERSION:
        print(f"analysis schema is stale: {payload.get('schema_version')} != {SCHEMA_VERSION}", file=sys.stderr)
        return 3
    current, _ = calculate_input_fingerprint(course_root)
    if current != payload.get("input_fingerprint"):
        print("analysis input fingerprint is stale", file=sys.stderr)
        return 3
    print("analysis input fingerprint verified")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--course-root", required=True, type=Path)
    parser.add_argument("--recent-year-span", type=int, default=5)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path, help="Verify an existing analysis against current source files")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    course_root = args.course_root.resolve()
    if args.recent_year_span < 1:
        print("--recent-year-span must be positive", file=sys.stderr)
        return 2
    if args.verify:
        return verify_existing(course_root, args.verify.resolve())
    try:
        payload = build_analysis(course_root, args.recent_year_span)
    except AnalysisBlocked as exc:
        payload = blocked_payload(exc.errors, exc.warnings, args.recent_year_span)
        write_json(args.output.resolve() if args.output else None, payload)
        return 2
    write_json(args.output.resolve() if args.output else None, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
