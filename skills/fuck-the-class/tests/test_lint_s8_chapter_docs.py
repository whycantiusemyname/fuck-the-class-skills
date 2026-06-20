from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import lint_s8_chapter_docs


def good_main_doc() -> str:
    paragraph = (
        "这一段先说明为什么要学这个动作，再说明题面中要看哪个信号，"
        "然后解释如果不这样起手会把哪一类题误判。"
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


def good_start_card() -> str:
    return """# 第 8 章 S10启动卡

> 这是进入 S10 问答/做题前的启动卡，不替代 `主干讲解.md`。
> 完全没学过本章时，先读主干讲解；读过但准备做题时，再读这份。

## 5 分钟地图
先分清正弦振荡和非正弦波形。

## 最小自测
问题：看到 RC 桥式振荡先看什么？
参考答案：先看环路相位和幅度条件。
"""


class S8ChapterDocsLintTests(unittest.TestCase):
    def test_accepts_default_three_layer_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            main = root / "第08章_信号产生电路_主干讲解.md"
            grounding = root / "第08章_信号产生电路_grounding.md"
            start = root / "第08章_信号产生电路_S10启动卡.md"
            main.write_text(good_main_doc(), encoding="utf-8")
            grounding.write_text("# grounding\n\n## 来源与边界\n课件第 1 页。\n\n## S10 主动 probe 种子\nprobe。", encoding="utf-8")
            start.write_text(good_start_card(), encoding="utf-8")
            report = lint_s8_chapter_docs.lint_knowledge_root(root)
            self.assertEqual(report.errors, [])

    def test_rejects_grounding_only_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "第08章_信号产生电路_grounding.md").write_text(
                "# grounding\n\n## 来源与边界\n课件。\n\n## S10 主动 probe 种子\nprobe。",
                encoding="utf-8",
            )
            report = lint_s8_chapter_docs.lint_knowledge_root(root)
            self.assertTrue(any("必须先有主干讲解" in error for error in report.errors))

    def test_explicit_grounding_only_mode_allows_single_grounding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            grounding = root / "第08章_信号产生电路_grounding.md"
            grounding.write_text("# grounding\n\n## 来源与边界\n课件。", encoding="utf-8")
            report = lint_s8_chapter_docs.lint_files([grounding], mode="grounding-only")
            self.assertEqual(report.errors, [])

    def test_rejects_start_card_without_main_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "第08章_信号产生电路_S10启动卡.md").write_text(good_start_card(), encoding="utf-8")
            report = lint_s8_chapter_docs.lint_knowledge_root(root)
            self.assertTrue(any("必须先有主干讲解" in error for error in report.errors))

    def test_legacy_starter_is_warning_not_default_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "第08章_信号产生电路_入门讲解.md").write_text("# 旧入门讲解\n\n旧文件。", encoding="utf-8")
            report = lint_s8_chapter_docs.lint_knowledge_root(root)
            self.assertEqual(report.errors, [])
            self.assertTrue(any("旧文件名" in warning for warning in report.warnings))

    def test_main_doc_missing_cognitive_slope_fails(self):
        text = "# 第 8 章 主干讲解\n\n## 这一章抓什么\n- 公式\n- 题型\n"
        report = lint_s8_chapter_docs.lint_main_doc(text, path=Path("第08章_主干讲解.md"))
        self.assertTrue(any("缺少必需标题" in error for error in report.errors))
        self.assertTrue(any("核心主题缺少" in error for error in report.errors))

    def test_bullet_dense_main_doc_fails(self):
        bullets = "\n".join(f"- 第 {i} 条" for i in range(40))
        text = good_main_doc() + "\n\n" + bullets * 8
        report = lint_s8_chapter_docs.lint_main_doc(text, path=Path("第08章_主干讲解.md"))
        self.assertTrue(any("bullet 行占比" in error for error in report.errors))


if __name__ == "__main__":
    unittest.main()
