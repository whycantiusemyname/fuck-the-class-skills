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
        "这一段先把本章的问题放进课程主线里，再说明学生做题时要先看哪个对象，"
        "接着解释微元、边界和公式如何互相牵动，避免把工具背成孤立结论。"
    )
    body = paragraph * 8
    return "\n\n".join([
        "# 第 8 章 信号产生电路 主干讲解",
        "## 这一章抓什么\n" + body,
        "## 阅读层次表\n| 层次 | 核心问题 | 典型动作 |\n|---|---|---|\n| 对象层 | 先判断题目要处理什么对象 | 画图、读条件、找边界 |\n| 机制层 | 看对象怎样被小量铺满 | 写微元、写状态链 |",
        "## 先建立整体直觉\n输出高电平 → 电容充电 → 达到阈值 → 比较器翻转 → 电容反向变化。\n" + body,
        "## 本章怎么串起来\n" + body,
        "## 分节主干",
        "### 正弦振荡为什么先看环路条件\n" + body + "\n\n其中每个符号都对应题目中的一个判断对象。环路条件可以写成\n\\[\n|AF|=1\n\\]\n这个条件表示信号绕环路一周后大小维持不变，题目中先看反馈网络和放大器，再看相位是否能回到同一状态。\n\n" + body,
        "### 非正弦波形为什么先看阈值和充放电路径\n" + body + "\n\n做题时先判断电容正在向哪个阈值移动，再判断比较器或开关什么时候翻转。最容易误判的是把瞬时方向看反，导致周期和幅度一起错。" + body,
        "## 解题流程\n1. **先认对象：** 判断题目问振荡条件、频率、阈值还是波形。\n2. **再找机制：** 看反馈、充放电或比较翻转怎样形成闭环。\n3. **最后算量：** 把公式放回题目条件中检查单位和符号。",
        "## 易错点\n- 只背公式但没有检查适用条件。\n- 把相位条件和幅度条件分开后忘了重新合并。\n- 看到电容就直接套周期公式，没有先判断充电方向。",
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

    def test_accepts_temp_style_natural_main_doc(self):
        report = lint_s8_chapter_docs.lint_main_doc(good_main_doc(), path=Path("第08章_主干讲解.md"))
        self.assertEqual(report.errors, [])

    def test_main_doc_missing_natural_structure_fails(self):
        text = "# 第 8 章 主干讲解\n\n## 这一章抓什么\n- 公式\n- 题型\n"
        report = lint_s8_chapter_docs.lint_main_doc(text, path=Path("第08章_主干讲解.md"))
        self.assertTrue(any("缺少必需结构" in error for error in report.errors))

    def test_repeated_fixed_template_fails(self):
        fixed_section = "\n\n".join([
            "### 直觉\n" + ("自然段解释。" * 40),
            "### 公式 / 条件\n其中每个符号都对应题目条件。",
            "### 公式为什么这样\n" + ("自然段解释。" * 40),
            "### 题目怎么起手\n" + ("自然段解释。" * 40),
            "### 易错点\n" + ("自然段解释。" * 40),
        ])
        text = good_main_doc() + "\n\n### 模板主题一\n" + fixed_section + "\n\n### 模板主题二\n" + fixed_section
        report = lint_s8_chapter_docs.lint_main_doc(text, path=Path("第08章_主干讲解.md"))
        self.assertTrue(any("固定五段模板重复出现" in error for error in report.errors))

    def test_bullet_dense_main_doc_warns(self):
        bullets = "\n".join(f"- 第 {i} 条" for i in range(40))
        text = good_main_doc() + "\n\n" + bullets * 8
        report = lint_s8_chapter_docs.lint_main_doc(text, path=Path("第08章_主干讲解.md"))
        self.assertFalse(any("bullet 行占比" in error for error in report.errors))
        self.assertTrue(any("bullet 行占比" in warning for warning in report.warnings))


if __name__ == "__main__":
    unittest.main()
