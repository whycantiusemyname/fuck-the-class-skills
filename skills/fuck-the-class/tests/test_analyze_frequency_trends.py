from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "analyze_frequency_trends.py"
SPEC = importlib.util.spec_from_file_location("analyze_frequency_trends", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FrequencyTrendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "10_题库").mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def write_tags(self, rows):
        body = [
            "# 标签库",
            "",
            "| 章节 | 能力主题 | 标准知识点标签 | 题数 |",
            "|---|---|---|---:|",
        ]
        body.extend(f"| {chapter} | {theme} | `{tag}` | {count} |" for chapter, theme, tag, count in rows)
        (self.root / "10_题库" / "_标签库.md").write_text("\n".join(body) + "\n", encoding="utf-8")

    def write_paper(self, filename, source, questions, paper_type=None, academic_year=None):
        meta = ["%%", "chapter: 综合", "question_type: 真题整卷"]
        meta.append(f"source: {source}")
        if paper_type:
            meta.append(f"paper_type: {paper_type}")
        if academic_year:
            meta.append(f"academic_year: {academic_year}")
        meta.append("%%")
        lines = [f"# {source}", "", *meta, ""]
        for question in questions:
            lines.extend([f"### {question['anchor']}", "", "%%"])
            lines.append(f"chapter: {question.get('chapter', '第一章')}")
            lines.append(f"question_type: {question['tag']}")
            lines.append(f"source: {source}")
            if "score" in question:
                lines.append(f"score: {question['score']}")
            if "question_form" in question:
                lines.append(f"question_form: {question['question_form']}")
            lines.extend(["%%", "", "题面", ""])
        (self.root / "10_题库" / filename).write_text("\n".join(lines), encoding="utf-8")

    def test_adjacent_metadata_and_form_precedence(self):
        self.write_tags([("第一章", "主题A", "标签A", 2)])
        self.write_paper(
            "2020-2021期末_题面整理.md",
            "2020-2021期末",
            [
                {"anchor": "20-21期末-选1", "tag": "标签A", "question_form": "证明题"},
                {"anchor": "20-21期末-算2", "tag": "标签A"},
            ],
        )
        definitions = MODULE.parse_tag_library(self.root / "10_题库" / "_标签库.md")
        questions, _ = MODULE.parse_question_files(self.root, definitions)
        self.assertEqual([question.question_form for question in questions], ["证明题", "计算题"])
        self.assertEqual([question.form_source for question in questions], ["explicit", "anchor"])

    def test_duplicate_unknown_tag_and_count_mismatch_block(self):
        self.write_tags([("第一章", "主题A", "标签A", 2)])
        self.write_paper(
            "2020-2021期末_题面整理.md",
            "2020-2021期末",
            [
                {"anchor": "重复-选1", "tag": "标签A"},
                {"anchor": "重复-选1", "tag": "未知标签"},
            ],
        )
        definitions = MODULE.parse_tag_library(self.root / "10_题库" / "_标签库.md")
        with self.assertRaises(MODULE.AnalysisBlocked) as caught:
            MODULE.parse_question_files(self.root, definitions)
        message = str(caught.exception)
        self.assertIn("未知标签", message)
        self.assertIn("标签计数不一致", message)

    def test_missing_theme_mapping_blocks(self):
        path = self.root / "10_题库" / "_标签库.md"
        path.write_text("| 章节 | 标准知识点标签 | 题数 |\n|---|---|---:|\n| 第一章 | `标签A` | 1 |\n", encoding="utf-8")
        with self.assertRaises(MODULE.AnalysisBlocked):
            MODULE.parse_tag_library(path)

    def test_unknown_year_excluded_and_ab_papers_merge(self):
        self.write_tags([("第一章", "主题A", "标签A", 3)])
        self.write_paper("A_题面整理.md", "2022-2023期末A", [{"anchor": "A-选1", "tag": "标签A"}])
        self.write_paper("B_题面整理.md", "2022-2023期末B", [{"anchor": "B-选1", "tag": "标签A"}])
        self.write_paper("缺卷头_题面整理.md", "缺卷头期末", [{"anchor": "未知-选1", "tag": "标签A"}])
        result = MODULE.build_analysis(self.root, 5)
        self.assertEqual(result["scope"]["paper_count"], 3)
        self.assertEqual(result["quality"]["unknown_year_paper_count"], 1)
        row = next(row for row in result["year_series"] if row["academic_year"] == "2022-2023")
        self.assertEqual(row["paper_count"], 2)

    def test_primary_trend_classifications(self):
        def metrics(rate, n=4):
            return {"year_count": n, "coverage_rate": rate, "coverage_numerator": round(rate * n)}

        recent_present = [
            {"present": False}, {"present": False}, {"present": True}, {"present": True}, {"present": True}
        ]
        self.assertEqual(MODULE.classify_primary_trend(metrics(0), metrics(0.75), recent_present), "首次成势")
        returned = [
            {"present": True}, {"present": False}, {"present": False}, {"present": True}, {"present": True}
        ]
        self.assertEqual(MODULE.classify_primary_trend(metrics(0.5), metrics(0.5), returned), "沉寂后回归")
        warming = [{"present": False}, {"present": True}, {"present": True}, {"present": True}]
        self.assertEqual(MODULE.classify_primary_trend(metrics(0.25), metrics(0.75), warming), "新近升温")
        cooling = [{"present": True}, {"present": True}, {"present": False}, {"present": False}]
        self.assertEqual(MODULE.classify_primary_trend(metrics(0.75), metrics(0.25), cooling), "明显降温")
        stable = [{"present": True}] * 5
        self.assertEqual(MODULE.classify_primary_trend(metrics(0.75), metrics(1.0), stable), "稳定核心")
        periodic = [{"present": True}, {"present": False}, {"present": True}, {"present": False}]
        self.assertEqual(MODULE.classify_primary_trend(metrics(0.5), metrics(0.5), periodic), "周期波动")

    def test_size_shift_and_unknown_score(self):
        historical = {
            "known_form_count": 4, "known_score_count": 3, "long_ratio": 0.0, "median_score": 3.0
        }
        recent = {
            "known_form_count": 4, "known_score_count": 3, "long_ratio": 0.75, "median_score": 10.0
        }
        self.assertIn("大题化", MODULE.classify_size_shift(historical, recent))
        small_historical = {
            "known_form_count": 4, "known_score_count": 3, "long_ratio": 0.75, "median_score": 10.0
        }
        small_recent = {
            "known_form_count": 4, "known_score_count": 3, "long_ratio": 0.0, "median_score": 3.0
        }
        self.assertIn("小题化", MODULE.classify_size_shift(small_historical, small_recent))
        self.assertIsNone(MODULE.parse_score("0"))
        self.assertIsNone(MODULE.parse_score("未标"))

    def test_tag_migration(self):
        rows = [("第一章", "主题A", "旧考法", 5), ("第一章", "主题A", "新考法", 6)]
        self.write_tags(rows)
        years = list(range(2015, 2025))
        old_left, new_left = 5, 6
        for year in years:
            questions = []
            if year < 2020 and old_left:
                questions.append({"anchor": f"{year}-算1", "tag": "旧考法", "score": 8})
                old_left -= 1
            if year >= 2020 and new_left:
                questions.append({"anchor": f"{year}-算2", "tag": "新考法", "score": 8})
                new_left -= 1
            if new_left and year == 2019:
                questions.append({"anchor": f"{year}-选3", "tag": "新考法", "score": 3})
                new_left -= 1
            if questions:
                self.write_paper(f"{year}-{year+1}期末_题面整理.md", f"{year}-{year+1}期末", questions)
        result = MODULE.build_analysis(self.root, 5)
        profile = result["themes"][0]["exam_profiles"]["期末"]
        self.assertIn("考法迁移", profile["secondary_trends"])

    def test_fingerprint_staleness(self):
        self.write_tags([("第一章", "主题A", "标签A", 1)])
        self.write_paper("卷_题面整理.md", "2020-2021期末", [{"anchor": "卷-选1", "tag": "标签A"}])
        result = MODULE.build_analysis(self.root, 5)
        output = self.root / "analysis.json"
        output.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(MODULE.verify_existing(self.root, output), 0)
        tag_file = self.root / "10_题库" / "_标签库.md"
        tag_file.write_text(tag_file.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.assertEqual(MODULE.verify_existing(self.root, output), 3)


if __name__ == "__main__":
    unittest.main()
