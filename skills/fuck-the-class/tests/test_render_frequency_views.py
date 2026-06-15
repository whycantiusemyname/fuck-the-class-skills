from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import analyze_frequency_trends as analyzer
import render_frequency_views as renderer


class RenderFrequencyViewsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "测试课"
        (self.root / "10_题库").mkdir(parents=True)
        (self.root / "40_派生视图").mkdir()
        (self.root / "10_题库" / "_标签库.md").write_text(
            "# 标签库\n\n| 章节 | 能力主题 | 标准知识点标签 | 题数 |\n"
            "|---|---|---|---:|\n| 第一章 | 主题A | `标签A` | 6 |\n",
            encoding="utf-8",
        )
        for year in range(2019, 2025):
            source = f"{year}-{year + 1}期末"
            text = (
                f"## {source}\n\n%%\nchapter: 综合\nquestion_type: 真题整卷｜期末\n"
                f"source: {source}\npaper_type: 期末\nacademic_year: {year}-{year + 1}\n%%\n\n"
                f"### {year}-期末-算1\n\n%%\nchapter: 第一章\nquestion_type: 标签A\n"
                f"source: {source}\nscore: 8\nquestion_form: 计算题\nocr_status: 已对照 PDF 复核\n%%\n\n题面\n"
            )
            (self.root / "10_题库" / f"{source}_题面整理.md").write_text(text, encoding="utf-8")
        self.analysis = self.root / "90_缓存" / "s2-frequency-analysis.json"
        self.analysis.parent.mkdir()
        self.analysis.write_text(
            json.dumps(analyzer.build_analysis(self.root, 5), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_full_render_and_verify(self):
        outputs = renderer.build_outputs(self.root, self.analysis)
        renderer.write_outputs(outputs)
        self.assertEqual(renderer.verify_outputs(outputs), 0)
        matrix = (self.root / "40_派生视图" / "考频矩阵.md").read_text(encoding="utf-8")
        theme = (self.root / "40_派生视图" / "主题题表.md").read_text(encoding="utf-8")
        self.assertTrue(matrix.startswith(renderer.DERIVED_MARKER))
        self.assertIn('x-axis ["T1"]', matrix)
        self.assertIn("schema 2.0", matrix)
        self.assertIn("高分杠杆", matrix)
        self.assertLess(matrix.index("```", matrix.index("主题覆盖")), matrix.index("数据表｜期末历史与近期覆盖"))
        self.assertLess(matrix.index("近期覆盖变化（百分点）"), matrix.index("数据表｜期末覆盖变化"))
        self.assertLess(matrix.index("近期已知分值负担"), matrix.index("数据表｜期末近期分值负担"))
        self.assertIn("## 主题A", theme)
        for year in range(2019, 2025):
            self.assertEqual(matrix.count(f"> | {year}-{year + 1} | 1 | 1 |"), 1)

    def test_verify_detects_manual_drift(self):
        outputs = renderer.build_outputs(self.root, self.analysis)
        renderer.write_outputs(outputs)
        path = self.root / "40_派生视图" / "考频矩阵.md"
        path.write_text(path.read_text(encoding="utf-8") + "手改\n", encoding="utf-8")
        self.assertEqual(renderer.verify_outputs(outputs), 2)

    def test_stale_analysis_is_rejected(self):
        tag_file = self.root / "10_题库" / "_标签库.md"
        tag_file.write_text(tag_file.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with self.assertRaises(renderer.RenderError):
            renderer.build_outputs(self.root, self.analysis)


if __name__ == "__main__":
    unittest.main()
