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

    def _write(self, name: str, content: str) -> Path:
        path = self.root / name
        path.write_text(content, encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
