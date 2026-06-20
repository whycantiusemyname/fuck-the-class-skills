from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import validate_course_artifacts as validator
import s8_digest_gate


def valid_s8_main_doc() -> str:
    paragraph = (
        "这一段说明本章问题怎样从前面章节自然出现，也说明题面中要先看什么，"
        "如果误判第一步会导致哪种常见错误。"
    )
    body = paragraph * 8
    return "\n\n".join([
        "# 第 8 章 信号产生电路 主干讲解",
        "## 本章放在课程里的位置\n" + body,
        "## 这一章抓什么\n" + body,
        "## 先建立整体直觉\n输出高电平 → 电容充电 → 达到阈值 → 比较器翻转 → 电容反向变化。\n" + body,
        "## 本章怎么串起来\n" + body,
        "## 核心主题一：正弦振荡",
        "### 直觉\n" + body,
        "### 公式 / 条件\n其中每个符号都对应题目中的一个判断对象。\n\\[\n|AF|=1\n\\]\n这个条件表示信号绕环路一周后大小维持不变，题目中先看反馈网络和放大器。",
        "### 公式为什么这样\n" + body,
        "### 题目怎么起手\n" + body,
        "### 易错点\n" + body,
        "## 典型题型入口\n" + body,
        "## 本章总图\n" + body,
        "## 复习检查\n- [ ] 我能解释环路条件。\n- [ ] 我能说出第一步。",
        "## 进入 S10 的问题入口\n" + body,
    ])


def valid_s8_start_card() -> str:
    return """# 第 8 章 S10启动卡

> 这是进入 S10 问答/做题前的启动卡，不替代 `主干讲解.md`。
> 完全没学过本章时，先读主干讲解；读过但准备做题时，再读这份。

## 最小自测
问题：看到 RC 桥式振荡先看什么？
参考答案：先看环路相位和幅度条件。
"""


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

    def test_s1_requires_new_intake_metadata_fields(self):
        (self.root / "10_题库" / "_标签库.md").write_text(
            "# 标签库\n\n| 章节 | 能力主题 | 标准知识点标签 | 题数 |\n"
            "|---|---|---|---:|\n| 第一章 | 主题A | `标签A` | 1 |\n",
            encoding="utf-8",
        )
        question = self.root / "10_题库" / "卷_题面整理.md"
        question.write_text(
            "## 卷\n\n### 卷-选1\n\n%%\nchapter: 第一章\nquestion_type: 标签A\nsource: 卷\n%%\n\n题面\n",
            encoding="utf-8",
        )
        errors, _, _ = validator.validate(self.root, "s1")
        self.assertTrue(any("文档级 source/paper_type/academic_year" in error for error in errors))
        self.assertTrue(any("question_form" in error and "ocr_status" in error for error in errors))

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
        path = self.root / "40_派生视图" / validator.S4_CANDIDATE_FILE
        path.write_text("# 本轮练习候选\n", encoding="utf-8")
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
        queue = self.root / "40_派生视图" / validator.S4_CANDIDATE_FILE
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

    def test_s10_accepts_minimal_initialized_course(self):
        events = self.root / "30_我的数据" / "学习事件.jsonl"
        events.write_text("", encoding="utf-8")
        errors, warnings, counts = validator.validate(self.root, "s10")
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(counts, {"control": 0, "latex": 0, "links": 0})

    def test_s10_rejects_invalid_jsonl_and_closed_fields(self):
        events = self.root / "30_我的数据" / "学习事件.jsonl"
        events.write_text(
            "{not json}\n"
            '{"event_id":"e1","time":"not-a-time","event_type":"probe","origin":"s10","evidence":"学生回答了问题","judgement":"错","coarse_wrong_cause":"概念错"}\n'
            '{"event_id":"e2","time":"2026-06-19T00:00:00+08:00","event_type":"attempt","origin":"s10","evidence":"证据","confidence":"sure"}\n'
            '{"event_id":"e2","time":"2026-06-19T00:00:00+08:00","event_type":"attempt","origin":"s3","evidence":"证据","diagnosis_hypothesis":"自行诊断","confidence":"low","next_probe":"追问"}\n',
            encoding="utf-8",
        )
        errors, _, _ = validator.validate(self.root, "s10")
        self.assertTrue(any("不是合法 JSON" in error for error in errors))
        self.assertTrue(any("time 不是 ISO 8601" in error for error in errors))
        self.assertTrue(any("非 attempt 事件不得写 judgement" in error for error in errors))
        self.assertTrue(any("非 attempt 事件不得写 coarse_wrong_cause" in error for error in errors))
        self.assertTrue(any("confidence 不在允许集合" in error for error in errors))
        self.assertTrue(any("event_id 重复" in error for error in errors))
        self.assertTrue(any("origin=s3 不得主动写 S10 字段" in error for error in errors))

    def test_s10_validates_required_origin_hypothesis_and_source_refs(self):
        question = self.root / "10_题库" / "卷_题面整理.md"
        question.write_text("# 卷\n\n### 锚点1\n", encoding="utf-8")
        events = self.root / "30_我的数据" / "学习事件.jsonl"
        events.write_text(
            '{"event_id":"e1","time":"2026-06-19T00:00:00+08:00","event_type":"repair","evidence":"证据","diagnosis_hypothesis":"方向混淆","confidence":"medium","source_refs":["[[测试课/10_题库/卷_题面整理#锚点1]]"]}\n'
            '{"event_id":"e2","time":"2026-06-19T00:00:00+08:00","event_type":"repair","origin":"s10","evidence":"证据","diagnosis_hypothesis":"方向混淆","confidence":"medium","next_probe":"再判断一个方向","source_refs":["不是链接"]}\n',
            encoding="utf-8",
        )
        errors, _, _ = validator.validate(self.root, "s10")
        self.assertTrue(any("缺少必填字段" in error and "origin" in error for error in errors))
        self.assertTrue(any("diagnosis_hypothesis 需要同时写 confidence 和 next_probe" in error for error in errors))
        self.assertTrue(any("source_refs 必须使用 wikilink" in error for error in errors))

    def test_s10_state_snapshot_requires_derived_marker(self):
        events = self.root / "30_我的数据" / "学习事件.jsonl"
        events.write_text("", encoding="utf-8")
        snapshot = self.root / "40_派生视图" / "学生状态快照.md"
        snapshot.write_text("# 学生状态快照\n", encoding="utf-8")
        errors, _, _ = validator.validate(self.root, "s10")
        self.assertTrue(any("派生文件标记" in error for error in errors))
        snapshot.write_text(validator.DERIVED_MARKER + "\n\n# 学生状态快照\n", encoding="utf-8")
        errors, _, _ = validator.validate(self.root, "s10")
        self.assertFalse(any("派生文件标记" in error for error in errors))

    def test_s8_accepts_valid_three_layer_outputs(self):
        source = self.root / "00_原材料" / "课件.pdf"
        source.parent.mkdir(exist_ok=True)
        source.write_bytes(b"source")
        main = self.root / "20_知识" / "第08章_信号产生电路_主干讲解.md"
        grounding = self.root / "20_知识" / "第08章_信号产生电路_grounding.md"
        start = self.root / "20_知识" / "第08章_信号产生电路_S10启动卡.md"
        main.write_text(valid_s8_main_doc(), encoding="utf-8")
        grounding.write_text("# grounding\n\n## 来源与边界\n课件第 1 页。\n\n## S10 主动 probe 种子\nprobe。", encoding="utf-8")
        start.write_text(valid_s8_start_card(), encoding="utf-8")
        s8_digest_gate.bind(self.root, "第08章", [source], [], [main, grounding, start])
        errors, _, _ = validator.validate(self.root, "s8")
        self.assertEqual(errors, [])

    def test_s8_allows_explicit_grounding_only_manifest_mode(self):
        source = self.root / "00_原材料" / "课件.pdf"
        source.parent.mkdir(exist_ok=True)
        source.write_bytes(b"source")
        grounding = self.root / "20_知识" / "第08章_信号产生电路_grounding.md"
        grounding.write_text("# grounding\n\n## 来源与边界\n课件第 1 页。\n\n## S10 主动 probe 种子\nprobe。", encoding="utf-8")
        s8_digest_gate.bind(self.root, "第08章-grounding", [source], [], [grounding], mode="grounding-only")
        errors, _, _ = validator.validate(self.root, "s8")
        self.assertFalse(any("必须先有主干讲解" in error for error in errors))

    def test_s8_rejects_default_manifest_without_main_doc(self):
        source = self.root / "00_原材料" / "课件.pdf"
        source.parent.mkdir(exist_ok=True)
        source.write_bytes(b"source")
        grounding = self.root / "20_知识" / "第08章_信号产生电路_grounding.md"
        grounding.write_text("# grounding\n\n## 来源与边界\n课件第 1 页。\n\n## S10 主动 probe 种子\nprobe。", encoding="utf-8")
        manifest_dir = self.root / "90_缓存" / "s8-digest" / "第08章"
        manifest_dir.mkdir(parents=True)
        manifest = manifest_dir / "digest.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "complete",
                    "chapter": "第08章",
                    "mode": "default",
                    "sources": [{"path": "00_原材料/课件.pdf", "sha256": s8_digest_gate.sha256_file(source)}],
                    "completions": [],
                    "outputs": [{"path": "20_知识/第08章_信号产生电路_grounding.md", "sha256": s8_digest_gate.sha256_file(grounding)}],
                    "warnings": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        errors, _, _ = validator.validate(self.root, "s8")
        self.assertTrue(any("必须先有主干讲解" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
