from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import validate_course_artifacts as validator


class ValidateCourseArtifactsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "测试课"
        for name in ("10_题库", "20_知识", "30_我的数据", "40_派生视图", "90_缓存"):
            (self.root / name).mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def test_chinese_heading_and_escaped_table_pipe_link(self):
        target = self.root / "10_题库" / "卷.md"
        target.write_text("# 卷\n\n### 中文锚点\n", encoding="utf-8")
        source = self.root / "20_知识" / "笔记.md"
        source.write_text(
            f"[[{self.root.name}/10_题库/卷#中文锚点\\|显示名]]\n",
            encoding="utf-8",
        )
        self.assertEqual(validator.link_issues(self.root, [source]), [])

    def test_cross_file_wikilinks_must_be_vault_root_relative(self):
        target = self.root / "10_题库" / "卷.md"
        target.write_text("# 卷\n", encoding="utf-8")
        source = self.root / "20_知识" / "笔记.md"
        source.write_text("[[../10_题库/卷|相对]]\n[[卷|裸文件名]]\n", encoding="utf-8")
        issues = validator.link_issues(self.root, [source])
        self.assertEqual(len(issues), 2)
        self.assertTrue(all("vault 根相对" in issue for issue in issues))

    def test_control_latex_and_broken_link_are_hard_errors(self):
        source = self.root / "10_题库" / "卷.md"
        source.write_text("# 卷\n\n坏字符\x0c frac{x} [[测试课/不存在|断链]]\n", encoding="utf-8")
        errors, _, counts = validator.validate(self.root, "s1")
        self.assertGreaterEqual(counts["control"], 1)
        self.assertGreaterEqual(counts["latex"], 1)
        self.assertGreaterEqual(counts["links"], 1)
        self.assertTrue(errors)

    def test_rightarrow_is_not_counted_as_right_delimiter(self):
        source = self.root / "10_题库" / "卷.md"
        source.write_text("# 卷\n\n$A \\Rightarrow B$\n", encoding="utf-8")
        self.assertEqual(
            validator.latex_issues(source, source.read_text(encoding="utf-8")),
            [],
        )

    def test_bare_math_is_warning_only(self):
        source = self.root / "10_题库" / "卷.md"
        source.write_text("# 卷\n\n疑似表达 \\frac{1}{x}，但不阻断。\n", encoding="utf-8")
        errors, warnings, _ = validator.validate(self.root, "s1")
        self.assertEqual(errors, [])
        self.assertTrue(any("疑似裸数学表达" in warning for warning in warnings))

    def test_missing_course_profile_is_compatible_but_malformed_profile_blocks(self):
        source = self.root / "10_题库" / "卷.md"
        source.write_text("# 卷\n", encoding="utf-8")
        errors, _, _ = validator.validate(self.root, "s1")
        self.assertEqual(errors, [])
        (self.root / "课程口径.md").write_text(
            "# 课程口径\n\n## 学习阶段\n\n大二\n",
            encoding="utf-8",
        )
        errors, _, _ = validator.validate(self.root, "s1")
        self.assertTrue(any("课程口径缺少章节" in error for error in errors))

    def test_quote_evidence_verification(self):
        source = self.root / "20_知识" / "对话.md"
        source.write_text("第一行\n最终讲通的话\n第三行\n", encoding="utf-8")
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        quote = "最终讲通的话"
        quote_hash = hashlib.sha256(quote.encode("utf-8")).hexdigest()
        blocker = self.root / "30_我的数据" / "卡点清单.md"
        blocker.write_text(
            "# 卡点清单\n\n"
            f"  quote_source: {self.root.name}/20_知识/对话.md\n"
            f"  quote_source_sha256: {source_hash}\n"
            "  quote_lines: 2-2\n"
            f"  quote_sha256: {quote_hash}\n"
            "  原文摘录:\n"
            "> 最终讲通的话\n",
            encoding="utf-8",
        )
        self.assertEqual(validator.quote_evidence_issues(self.root), [])
        blocker.write_text(blocker.read_text(encoding="utf-8").replace("最终讲通的话\n", "被改写的话\n", 1), encoding="utf-8")
        self.assertTrue(validator.quote_evidence_issues(self.root))

    def test_derived_marker_required(self):
        path = self.root / "40_派生视图" / "当日队列.md"
        path.write_text("# 当日队列\n", encoding="utf-8")
        errors, _, _ = validator.validate(self.root, "s4")
        self.assertTrue(any("派生文件标记" in error for error in errors))

    def test_s4_and_s9_reject_pending_ocr_questions(self):
        question = self.root / "10_题库" / "卷_题面整理.md"
        question.write_text(
            "## 卷\n\n### 卷-选1\n\n%%\nchapter: 第一章\nquestion_type: 标签A\n"
            "source: 卷\nocr_status: 待复核\n%%\n\n题面\n"
            "> [!note]- 解答｜状态：独立解答未对照\n> 解答\n> 起手：第一步\n",
            encoding="utf-8",
        )
        queue = self.root / "40_派生视图" / "当日队列.md"
        queue.write_text(
            validator.DERIVED_MARKER + f"\n\n[[{self.root.name}/10_题库/卷_题面整理#卷-选1|题目]]\n",
            encoding="utf-8",
        )
        s4_errors, _, _ = validator.validate(self.root, "s4")
        s9_errors, _, _ = validator.validate(self.root, "s9")
        self.assertTrue(any("队列消费了待复核题" in error for error in s4_errors))
        self.assertTrue(any("含 S9 解答块" in error for error in s9_errors))

    def test_s6_starter_requires_provenance(self):
        cram = self.root / "40_派生视图" / "冲刺包.md"
        cram.write_text(validator.DERIVED_MARKER + "\n\n- 起手：现场编的第一步\n", encoding="utf-8")
        errors, _, _ = validator.validate(self.root, "s6")
        self.assertTrue(any("缺少允许的来源" in error for error in errors))
        cram.write_text(validator.DERIVED_MARKER + "\n\n- 起手：待 S9\n", encoding="utf-8")
        errors, _, _ = validator.validate(self.root, "s6")
        self.assertFalse(any("起手" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
