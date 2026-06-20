from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import course_profile


class CourseProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "课程"
        self.root.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_initialize_with_stage_and_scope(self):
        path = course_profile.initialize(
            self.root,
            "大二下",
            ["期末覆盖第 1-6 章"],
            ["第 6 章为重点"],
            ["附录不考"],
            False,
        )
        profile = course_profile.parse_profile(path)
        self.assertEqual(profile["学习阶段"], "大二下")
        self.assertIn("期末覆盖第 1-6 章", profile["已确认教学/考试范围"])

    def test_default_stage_is_unset(self):
        path = course_profile.initialize(self.root, None, [], [], [], False)
        profile = course_profile.parse_profile(path)
        self.assertEqual(profile["学习阶段"], "未设置")
        self.assertEqual(profile["已确认教学/考试范围"], "未设置")

    def test_update_preserves_unspecified_fields(self):
        course_profile.initialize(
            self.root,
            "大二下",
            ["期末覆盖第 1-6 章"],
            ["第 6 章为重点"],
            ["附录不考"],
            False,
        )
        path = course_profile.update(self.root, learning_stage="考前")
        profile = course_profile.parse_profile(path)
        self.assertEqual(profile["学习阶段"], "考前")
        self.assertIn("期末覆盖第 1-6 章", profile["已确认教学/考试范围"])
        self.assertIn("第 6 章为重点", profile["教师重点与主线/补充关系"])

    def test_list_items_must_be_single_line(self):
        with self.assertRaises(course_profile.CourseProfileError):
            course_profile.render_profile("大二", ["第一行\n第二行"], [], [])

    def test_missing_profile_is_legacy_compatible(self):
        self.assertIsNone(course_profile.load_profile(self.root))

    def test_stage_does_not_change_scope_fields(self):
        first = course_profile.parse_profile(
            self._write("first.md", course_profile.render_profile("大一", ["课件全部"], [], []))
        )
        second = course_profile.parse_profile(
            self._write("second.md", course_profile.render_profile("研一", ["课件全部"], [], []))
        )
        self.assertEqual(course_profile.scope_fields(first), course_profile.scope_fields(second))

    def test_malformed_existing_profile_is_rejected(self):
        path = self._write("课程口径.md", "# 课程口径\n\n## 学习阶段\n\n大二\n")
        with self.assertRaises(course_profile.CourseProfileError):
            course_profile.parse_profile(path)

    def test_s8_scope_rule_has_no_course_specific_term_examples(self):
        workflow = (Path(__file__).parents[1] / "references" / "workflow-s8-courseware-digest.md").read_text(
            encoding="utf-8"
        )
        for term in ("limsup", "Cauchy criteria", "Hessian", "Jacobian"):
            self.assertNotIn(term, workflow)

    def test_s8_runtime_grounding_rules_are_explicit(self):
        workflow = (Path(__file__).parents[1] / "references" / "workflow-s8-courseware-digest.md").read_text(
            encoding="utf-8"
        )
        for required in (
            "AI tutor grounding + 学生最小启动入口",
            "默认目标不是写一篇越长越好的静态讲义",
            "完整主干讲义仍可生成，但只在用户明确要求",
            "让学生从“无问题状态”进入“能做第一步/能追问/能暴露错误”的状态",
            "这一章解决什么类型的问题？",
            "看到题目先看什么信号？",
            "第一动作是什么？",
            "公式/方法成立条件是什么？",
            "立刻进入 S10 的最小 probe 是什么？",
            "来源与边界",
            "S10 主动 probe 种子",
            "完整讲义不是默认主学习场",
            "段落适合电子阅读",
            "长段必须拆",
        ):
            self.assertIn(required, workflow)
        self.assertNotIn("通俗解释", workflow)

    def _write(self, name: str, content: str) -> Path:
        path = self.root / name
        path.write_text(content, encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
