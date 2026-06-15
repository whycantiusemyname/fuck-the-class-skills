#!/usr/bin/env python3
"""Render Fuck The Class S2 Markdown views deterministically from analysis JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import analyze_frequency_trends as analyzer


DERIVED_MARKER = "> 派生文件，可重新生成，勿手改。"
ROLE_PRIORITY = {
    "高分杠杆": 1,
    "高频主力": 2,
    "中频主干": 3,
    "低频风险": 4,
    "低频观察": 5,
    "该卷型未覆盖": 6,
}
GROWTH_TRENDS = {"首次成势", "沉寂后回归", "新近升温"}
METHOD_TRENDS = {"大题化", "小题化", "考法迁移"}


class RenderError(Exception):
    pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RenderError(f"无法读取分析 JSON：{exc}") from exc
    if payload.get("status") != "complete":
        raise RenderError("分析 JSON 状态不是 complete")
    if payload.get("schema_version") != analyzer.SCHEMA_VERSION:
        raise RenderError(
            f"分析 JSON schema 不兼容：{payload.get('schema_version')}，需要 {analyzer.SCHEMA_VERSION}"
        )
    return payload


def verify_fingerprint(course_root: Path, payload: dict[str, Any]) -> None:
    current, _ = analyzer.calculate_input_fingerprint(course_root)
    if current != payload.get("input_fingerprint"):
        raise RenderError("分析 JSON 输入指纹已过期")


def half_up_percent(value: float | None) -> int | None:
    return None if value is None else int(analyzer.round_half_up(value * 100))


def fmt_rate(value: float | None) -> str:
    percent = half_up_percent(value)
    return "—" if percent is None else f"{percent}%"


def fmt_delta(value: float | None) -> str:
    percent = half_up_percent(value)
    if percent is None:
        return "—"
    return f"{percent:+d}pp"


def fmt_number(value: float | int | None) -> str:
    if value is None:
        return "—"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def fmt_coverage(period: dict[str, Any]) -> str:
    return f"{period['coverage_numerator']}/{period['coverage_denominator']}（{fmt_rate(period['coverage_rate'])}）"


def fmt_distribution(distribution: dict[str, float]) -> str:
    if not distribution:
        return "无已知题型"
    rows = sorted(distribution.items(), key=lambda item: (-item[1], item[0]))
    return "；".join(f"{name} {fmt_rate(share)}" for name, share in rows)


def trend_text(profile: dict[str, Any]) -> str:
    values = [profile["primary_trend"], *profile.get("secondary_trends", [])]
    return " · ".join(values)


def escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def wiki(target: str, label: str, *, table: bool = False) -> str:
    return f"[[{target}|{label}]]"


def question_link(course_name: str, representative: dict[str, Any], *, table: bool = False) -> str:
    target = f"{course_name}/10_题库/{representative['file']}#{representative['anchor']}"
    return wiki(target, representative["anchor"], table=table)


def theme_link(course_name: str, theme: str, label: str | None = None, *, table: bool = False) -> str:
    target = f"{course_name}/40_派生视图/主题题表#{theme}"
    return wiki(target, label or theme, table=table)


def collapsed_table(title: str, headers: list[str], rows: Iterable[list[str]]) -> list[str]:
    lines = [f"> [!info]- {title}", "> | " + " | ".join(headers) + " |", "> | " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("> | " + " | ".join(escape_table(str(value)) for value in row) + " |")
    return lines + [""]


def profile_sort_key(item: dict[str, Any], paper_type: str) -> tuple[Any, ...]:
    profile = item["exam_profiles"][paper_type]
    recent = profile["recent"]
    return (
        profile["trend_priority"],
        -abs(profile["coverage_delta"]),
        -(recent["coverage_rate"] or 0.0),
        -(recent["known_score_total"] or 0.0),
        item["name"],
    )


def importance_sort_key(item: dict[str, Any], paper_type: str) -> tuple[Any, ...]:
    profile = item["exam_profiles"][paper_type]
    recent = profile["recent"]
    return (
        ROLE_PRIORITY[profile["importance_role"]],
        profile["trend_priority"],
        -(recent["coverage_rate"] or 0.0),
        -(recent["known_score_total"] or 0.0),
        item["name"],
    )


def alert_sentence(course_name: str, item: dict[str, Any], paper_type: str, kind: str) -> str:
    profile = item["exam_profiles"][paper_type]
    historical, recent = profile["historical"], profile["recent"]
    label = item["name"]
    link = theme_link(course_name, item.get("theme", label), label)
    reps = profile["representatives"]["recent"]
    rep_text = "、".join(question_link(course_name, rep) for rep in reps) or "无近期代表题"
    base = (
        f"- **{link}｜{trend_text(profile)}：** 历史 {fmt_coverage(historical)} → "
        f"近期 {fmt_coverage(recent)}，{fmt_delta(profile['coverage_delta'])}"
    )
    if kind == "method":
        details: list[str] = []
        if "大题化" in profile["secondary_trends"] or "小题化" in profile["secondary_trends"]:
            details.append(
                f"长题 {fmt_rate(historical['long_ratio'])} → {fmt_rate(recent['long_ratio'])}，"
                f"中位分 {fmt_number(historical['median_score'])} → {fmt_number(recent['median_score'])}"
            )
        change = profile.get("tag_change")
        if change and change.get("migrated"):
            details.append(
                f"{change['historical_dominant_tag']} {fmt_rate(change['historical_dominant_share'])} → "
                f"{change['recent_dominant_tag']} {fmt_rate(change['recent_dominant_share'])}"
            )
        if details:
            base += "；" + "；".join(details)
    return base + f"；近期题：{rep_text}。"


def parse_starters(course_root: Path) -> dict[str, str]:
    starters: dict[str, str] = {}
    for path in sorted((course_root / "10_题库").glob("*题面整理.md")):
        text = path.read_text(encoding="utf-8-sig")
        matches = list(re.finditer(r"^###\s+(.+?)\s*$", text, flags=re.MULTILINE))
        for index, match in enumerate(matches):
            block = text[match.end() : matches[index + 1].start() if index + 1 < len(matches) else len(text)]
            status = re.search(r"^> \[!note\]- 解答｜状态：(.+?)\s*$", block, flags=re.MULTILINE)
            if not status or status.group(1).strip() == "存疑":
                continue
            starter = re.search(r"^> 起手：(.+?)\s*$", block, flags=re.MULTILINE)
            if starter:
                starters[match.group(1).strip()] = starter.group(1).strip()
    return starters


def chart_lines(course_name: str, paper_type: str, themes: list[dict[str, Any]], theme_ids: dict[str, str]) -> list[str]:
    ids = [theme_ids[item["name"]] for item in themes]
    historical = [half_up_percent(item["exam_profiles"][paper_type]["historical"]["coverage_rate"]) or 0 for item in themes]
    recent = [half_up_percent(item["exam_profiles"][paper_type]["recent"]["coverage_rate"]) or 0 for item in themes]
    deltas = [half_up_percent(item["exam_profiles"][paper_type]["coverage_delta"]) or 0 for item in themes]
    scores = [item["exam_profiles"][paper_type]["recent"]["known_score_total"] or 0 for item in themes]
    score_max = max(10, int(analyzer.round_half_up(max(scores) + 5, 0)))
    quoted_ids = ", ".join(json.dumps(value, ensure_ascii=False) for value in ids)
    outputs: list[str] = []
    charts = [
        (
            f"{paper_type}主题覆盖：柱=历史，线=近期",
            "覆盖率 %",
            "0 --> 100",
            [f"    bar {json.dumps(historical)}", f"    line {json.dumps(recent)}"],
            "历史与近期覆盖",
            ["编号", "主题", "历史覆盖", "近期覆盖"],
            [
                [theme_ids[item["name"]], theme_link(course_name, item["name"], table=True), fmt_coverage(item["exam_profiles"][paper_type]["historical"]), fmt_coverage(item["exam_profiles"][paper_type]["recent"])]
                for item in themes
            ],
        ),
        (
            f"{paper_type}近期覆盖变化（百分点）",
            "百分点",
            "-100 --> 100",
            [f"    bar {json.dumps(deltas)}"],
            "覆盖变化",
            ["编号", "主题", "变化", "趋势"],
            [
                [theme_ids[item["name"]], theme_link(course_name, item["name"], table=True), fmt_delta(item["exam_profiles"][paper_type]["coverage_delta"]), trend_text(item["exam_profiles"][paper_type])]
                for item in themes
            ],
        ),
        (
            f"{paper_type}近期已知分值负担",
            "分值合计",
            f"0 --> {score_max}",
            [f"    bar {json.dumps(scores)}"],
            "近期分值负担",
            ["编号", "主题", "近期已知分值", "近期中位分", "近期每卷题数"],
            [
                [theme_ids[item["name"]], theme_link(course_name, item["name"], table=True), fmt_number(item["exam_profiles"][paper_type]["recent"]["known_score_total"]), fmt_number(item["exam_profiles"][paper_type]["recent"]["median_score"]), fmt_number(item["exam_profiles"][paper_type]["recent"]["average_questions_per_paper"])]
                for item in themes
            ],
        ),
    ]
    for title, y_label, y_range, series, table_title, headers, rows in charts:
        outputs.extend([
            "```mermaid",
            "xychart-beta",
            f"    title {json.dumps(title, ensure_ascii=False)}",
            f"    x-axis [{quoted_ids}]",
            f"    y-axis {json.dumps(y_label, ensure_ascii=False)} {y_range}",
            *series,
            "```",
            "",
        ])
        outputs.extend(collapsed_table(f"数据表｜{paper_type}{table_title}", headers, rows))
    return outputs


def render_matrix(course_root: Path, payload: dict[str, Any]) -> str:
    course_name = course_root.name
    themes = payload["themes"]
    tags = payload["tags"]
    paper_types = list(payload["scope"]["paper_types"])
    theme_ids = {item["name"]: f"T{index}" for index, item in enumerate(themes, start=1)}
    quality = payload["quality"]
    lines = [
        DERIVED_MARKER,
        "",
        f"# {course_name}考频矩阵",
        "",
        f"- 证据缓存：`90_缓存/s2-frequency-analysis.json`，schema {payload['schema_version']}，输入指纹 `{payload['input_fingerprint'][:12]}…`。",
        f"- 范围：{payload['scope']['paper_count']} 份卷、{payload['scope']['unique_anchor_count']} 个唯一题目锚点、{payload['scope']['tag_count']} 个知识点标签、{payload['scope']['theme_count']} 个能力主题。",
        f"- 题型来源：显式 {quality['question_form_explicit']}，锚点推断 {quality['question_form_inferred']}，未判定 {quality['question_form_unknown']}。",
        f"- OCR 状态：显式 {quality['ocr_status_explicit']}，旧题兼容 {quality['ocr_status_legacy_default']}。",
        "",
        "## 一眼看重点",
        "",
    ]
    for paper_type in paper_types:
        lines.extend([f"### {paper_type}趋势总览", "", *chart_lines(course_name, paper_type, themes, theme_ids)])

    lines.extend(["## 趋势预警", ""])
    combined = [*themes, *tags]
    for paper_type in paper_types:
        lines.extend([f"### {paper_type}", "", "#### 升温与回归"])
        growth = [item for item in combined if item["exam_profiles"][paper_type]["primary_trend"] in GROWTH_TRENDS]
        growth.sort(key=lambda item: profile_sort_key(item, paper_type))
        lines.extend(alert_sentence(course_name, item, paper_type, "growth") for item in growth[:8])
        if not growth:
            lines.append("- 暂无达到阈值的升温或回归项。")
        lines.extend(["", "#### 题型与考法变化"])
        method = [item for item in combined if METHOD_TRENDS & set(item["exam_profiles"][paper_type]["secondary_trends"])]
        method.sort(key=lambda item: profile_sort_key(item, paper_type))
        lines.extend(alert_sentence(course_name, item, paper_type, "method") for item in method[:8])
        if not method:
            lines.append("- 暂无达到阈值的题型或考法变化。")
        lines.extend(["", "#### 明显降温"])
        cooling = [item for item in combined if item["exam_profiles"][paper_type]["primary_trend"] == "明显降温"]
        cooling.sort(key=lambda item: profile_sort_key(item, paper_type))
        lines.extend(alert_sentence(course_name, item, paper_type, "cooling") for item in cooling[:8])
        if not cooling:
            lines.append("- 暂无达到阈值的明显降温项。")
        lines.append("")

    lines.extend(["## 重点判断", ""])
    for paper_type in paper_types:
        lines.append(f"### {paper_type}")
        ranked = sorted(themes, key=lambda item: importance_sort_key(item, paper_type))[:3]
        for item in ranked:
            profile = item["exam_profiles"][paper_type]
            recent = profile["recent"]
            lines.append(
                f"- **{theme_link(course_name, item['name'])}｜{profile['importance_role']}：** "
                f"近期覆盖 {fmt_coverage(recent)}，近期已知分值 {fmt_number(recent['known_score_total'])}，"
                f"趋势为 {trend_text(profile)}。"
            )
        lines.append("")

    lines.extend(["## 期中与期末重要性", ""])
    for paper_type in paper_types:
        rows = []
        for item in sorted(themes, key=lambda value: importance_sort_key(value, paper_type)):
            profile = item["exam_profiles"][paper_type]
            rows.append([
                theme_link(course_name, item["name"], table=True),
                profile["importance_role"],
                fmt_coverage(profile["historical"]),
                fmt_coverage(profile["recent"]),
                fmt_number(profile["recent"]["known_score_total"]),
                trend_text(profile),
            ])
        lines.extend(collapsed_table(f"{paper_type}主题重要性", ["主题", "考试角色", "历史覆盖", "近期覆盖", "近期分值", "趋势"], rows))

    lines.extend(["## 高频排序", ""])
    for paper_type in paper_types:
        rows = []
        ranked_tags = sorted(tags, key=lambda item: importance_sort_key(item, paper_type))
        for index, item in enumerate(ranked_tags, start=1):
            profile = item["exam_profiles"][paper_type]
            rows.append([
                str(index),
                theme_link(course_name, item["theme"], item["name"], table=True),
                profile["importance_role"],
                fmt_coverage(profile["recent"]),
                fmt_number(profile["recent"]["average_questions_per_paper"]),
                fmt_number(profile["recent"]["known_score_total"]),
                trend_text(profile),
            ])
        lines.extend(collapsed_table(f"{paper_type}知识点排序", ["序", "知识点", "角色", "近期覆盖", "每卷题数", "近期分值", "趋势"], rows))

    lines.extend(["## 低频与降温信号", ""])
    for paper_type in paper_types:
        selected = [
            item for item in tags
            if item["exam_profiles"][paper_type]["importance_role"] in {"低频风险", "低频观察", "该卷型未覆盖"}
            or item["exam_profiles"][paper_type]["primary_trend"] == "明显降温"
        ]
        selected.sort(key=lambda item: importance_sort_key(item, paper_type))
        rows = []
        for item in selected:
            profile = item["exam_profiles"][paper_type]
            rows.append([
                theme_link(course_name, item["theme"], item["name"], table=True),
                profile["importance_role"],
                fmt_coverage(profile["historical"]),
                fmt_coverage(profile["recent"]),
                fmt_delta(profile["coverage_delta"]),
                trend_text(profile),
            ])
        lines.extend(collapsed_table(f"{paper_type}低频与降温", ["知识点", "角色", "历史覆盖", "近期覆盖", "变化", "趋势"], rows))

    lines.extend(["## 完整趋势与分卷证据附录", ""])
    for paper_type in paper_types:
        trend_rows = []
        for item in sorted(tags, key=lambda value: profile_sort_key(value, paper_type)):
            profile = item["exam_profiles"][paper_type]
            reps = "、".join(question_link(course_name, rep, table=True) for rep in profile["representatives"]["recent"]) or "—"
            trend_rows.append([
                theme_link(course_name, item["theme"], item["name"], table=True),
                profile["importance_role"],
                trend_text(profile),
                fmt_coverage(profile["historical"]),
                fmt_coverage(profile["recent"]),
                fmt_delta(profile["coverage_delta"]),
                reps,
            ])
        lines.extend(collapsed_table(f"{paper_type}完整趋势", ["知识点", "角色", "趋势", "历史覆盖", "近期覆盖", "变化", "代表题"], trend_rows))

        year_rows = [
            [row["academic_year"], str(row["paper_count"]), str(row["question_count"])]
            for row in payload["year_series"] if row["paper_type"] == paper_type
        ]
        lines.extend(collapsed_table(f"{paper_type}年度桶", ["学年", "试卷数", "题数"], year_rows))

        paper_rows = []
        for row in payload["paper_series"]:
            if row["paper_type"] != paper_type or row["academic_year"] is None:
                continue
            paper_rows.append([row["academic_year"], row["source"], str(row["question_count"])])
        lines.extend(collapsed_table(f"{paper_type}分卷证据", ["学年", "来源", "题数"], paper_rows))

    lines.extend(["## 数据质量", ""])
    unknown = [row for row in payload["paper_series"] if row["academic_year"] is None]
    if unknown:
        lines.append("- 未知学年试卷只参加总频次，不进入年度趋势：" + "、".join(row["source"] for row in unknown) + "。")
    else:
        lines.append("- 未知学年试卷 0 份。")
    lines.append(f"- OCR 状态分布：{json.dumps(quality['ocr_status_counts'], ensure_ascii=False, sort_keys=True)}。")
    lines.append("- 本文件由确定性渲染器完整生成；局部手改会被 `--verify` 拒绝。")
    return "\n".join(lines).rstrip() + "\n"


def render_theme_table(course_root: Path, payload: dict[str, Any]) -> str:
    course_name = course_root.name
    starters = parse_starters(course_root)
    paper_types = list(payload["scope"]["paper_types"])
    lines = [
        DERIVED_MARKER,
        "",
        f"# {course_name}主题题表",
        "",
        f"本题表由 schema {payload['schema_version']} 趋势 JSON 确定性生成，覆盖 {payload['scope']['unique_anchor_count']} 个题目锚点。",
        "",
        f"返回：{wiki(f'{course_name}/40_派生视图/考频矩阵#趋势预警', '考频矩阵·趋势预警')}",
        "",
    ]
    for item in payload["themes"]:
        lines.extend([f"## {item['name']}", ""])
        rows = []
        starter_rows: list[str] = []
        for paper_type in paper_types:
            profile = item["exam_profiles"][paper_type]
            historical, recent = profile["historical"], profile["recent"]
            lines.append(
                f"- **{paper_type}｜{profile['importance_role']}｜{trend_text(profile)}：** "
                f"历史 {fmt_coverage(historical)} → 近期 {fmt_coverage(recent)}，{fmt_delta(profile['coverage_delta'])}。"
            )
            change = profile.get("tag_change") or {}
            dominant = "—"
            if change.get("historical_dominant_tag") or change.get("recent_dominant_tag"):
                dominant = (
                    f"{change.get('historical_dominant_tag') or '—'} {fmt_rate(change.get('historical_dominant_share'))} → "
                    f"{change.get('recent_dominant_tag') or '—'} {fmt_rate(change.get('recent_dominant_share'))}"
                )
            representatives = [*profile["representatives"]["historical"], *profile["representatives"]["recent"]]
            rep_text = "、".join(question_link(course_name, rep, table=True) for rep in representatives) or "—"
            rows.append([
                paper_type,
                profile["importance_role"],
                trend_text(profile),
                f"{fmt_coverage(historical)} → {fmt_coverage(recent)}（{fmt_delta(profile['coverage_delta'])}）",
                f"{fmt_distribution(historical['form_distribution'])} → {fmt_distribution(recent['form_distribution'])}",
                dominant,
                rep_text,
            ])
            for representative in profile["representatives"]["recent"]:
                starter = starters.get(representative["anchor"])
                if starter:
                    starter_rows.append(f"- 起手｜{question_link(course_name, representative)}：{starter}")
        lines.append("")
        lines.extend(collapsed_table(f"趋势与代表题｜{item['name']}", ["卷型", "角色", "趋势", "覆盖变化", "题型结构", "主导考法", "代表题"], rows))
        lines.extend(starter_rows)
        if starter_rows:
            lines.append("")
    quality = payload["quality"]
    lines.extend([
        "## 数据质量",
        "",
        f"- question_form：显式 {quality['question_form_explicit']}，锚点推断 {quality['question_form_inferred']}，未判定 {quality['question_form_unknown']}。",
        f"- OCR 状态：显式 {quality['ocr_status_explicit']}，旧题兼容 {quality['ocr_status_legacy_default']}。",
        f"- 未知学年试卷 {quality['unknown_year_paper_count']} 份，只参加总频次。",
        "- 能力主题来自标签库唯一映射；S2 不修复源数据。",
    ])
    return "\n".join(lines).rstrip() + "\n"


def build_outputs(course_root: Path, analysis_path: Path) -> dict[Path, str]:
    payload = read_json(analysis_path)
    verify_fingerprint(course_root, payload)
    view_dir = course_root / "40_派生视图"
    return {
        view_dir / "考频矩阵.md": render_matrix(course_root, payload),
        view_dir / "主题题表.md": render_theme_table(course_root, payload),
    }


def write_outputs(outputs: dict[Path, str]) -> None:
    staged: list[tuple[Path, Path]] = []
    try:
        for path, text in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(text, encoding="utf-8", newline="\n")
            staged.append((temporary, path))
        for temporary, path in staged:
            temporary.replace(path)
    finally:
        for temporary, _ in staged:
            if temporary.exists():
                temporary.unlink()


def verify_outputs(outputs: dict[Path, str]) -> int:
    mismatches: list[str] = []
    for path, expected in outputs.items():
        if not path.exists():
            mismatches.append(f"缺少派生文件：{path}")
            continue
        actual = path.read_text(encoding="utf-8-sig")
        if actual != expected:
            mismatches.append(f"派生文件与 JSON 不一致：{path}")
    if mismatches:
        print("\n".join(mismatches), file=sys.stderr)
        return 2
    print("S2 Markdown 与分析 JSON 一致")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--course-root", required=True, type=Path)
    parser.add_argument("--analysis", required=True, type=Path)
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        outputs = build_outputs(args.course_root.resolve(), args.analysis.resolve())
    except RenderError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    if args.verify:
        return verify_outputs(outputs)
    write_outputs(outputs)
    print("S2 Markdown 已确定性生成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
