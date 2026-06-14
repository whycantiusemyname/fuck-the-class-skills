# Fuck The Class Skills

Fuck The Class 是一套面向考试冲刺的 Codex 技能集合。它把课程资料、试卷、作业、做题截图、错题记录和 AI 学习对话整理成可追踪、可核验、可重复生成的复习资产，而不是替用户强行安排学习节奏。

本仓库包含两个配套技能：

- `fuck-the-class`：核心应试工作流，覆盖课程初始化、试卷入库、考频与趋势分析、批改记录、练习队列、错因复盘、冲刺包、学习对话提取、课件梳理和核验解答。
- `pdf-to-markdown`：PDF 转 Obsidian Markdown 的高置信度流水线，负责 MinerU 解析、分段修复、逐页视觉核验和哈希绑定的完成证书。

二者放在一起，是因为 Fuck The Class 在处理 PDF 试卷和 PDF/PPT 课件时，需要一个明确、可验证的文档转换入口。`pdf-to-markdown` 只在所有文本与视觉检查通过后交付最终 Markdown，避免下游复习资料建立在不完整草稿上。

## 项目特点

- 用户控制节奏：一次执行一个明确动作，不自动生成日程。
- 单一事实来源：题目、标签、做题记录和派生视图各有固定归属。
- 确定性分析：考频、时间趋势和题型变化由脚本生成，不靠临时猜测。
- 可核验的 PDF 摄取：未通过文本、视觉与哈希门禁的转换结果不会被当作最终资料。
- 面向 Obsidian：目录、链接、图片和 Markdown 输出适合本地知识库管理。

## 仓库结构

```text
skills/
  fuck-the-class/
    SKILL.md
    agents/
    references/
    scripts/
    tests/
  pdf-to-markdown/
    SKILL.md
    agents/
    references/
    scripts/
    tests/
requirements-pdf.txt
```

## 安装

将两个技能目录复制到 Codex 技能目录：

```powershell
$skillsHome = Join-Path $HOME ".codex\skills"
Copy-Item -Recurse -Force .\skills\fuck-the-class $skillsHome
Copy-Item -Recurse -Force .\skills\pdf-to-markdown $skillsHome
```

PDF 工作流需要 Python 3.10+，并可通过以下命令安装依赖：

```powershell
python -m pip install -r requirements-pdf.txt
```

调用 MinerU 前，需要设置 `MINERU_API_TOKEN`。不要把真实令牌写入仓库。

## 使用

在 Codex 中直接描述任务，或明确点名技能：

```text
使用 $fuck-the-class 初始化这门课程。
使用 $fuck-the-class 把这套试卷入库并重新生成考频分析。
使用 $pdf-to-markdown 把这个 PDF 转成经过核验的 Obsidian Markdown。
```

`fuck-the-class` 的主要动作编号为 S0-S9，具体边界和产物以 [`skills/fuck-the-class/SKILL.md`](skills/fuck-the-class/SKILL.md) 为准。PDF 转换的完成门禁以 [`skills/pdf-to-markdown/SKILL.md`](skills/pdf-to-markdown/SKILL.md) 为准。

## 测试

```powershell
python -m unittest discover -s skills\fuck-the-class\tests -v
python -m unittest discover -s skills\pdf-to-markdown\tests -v
```

测试不会替代真实 PDF 转换中的 MinerU、分段文本修复和逐页视觉核验。

## 安全说明

- 仓库不包含 MinerU API 令牌或课程原始资料。
- `00_原材料/` 在 Fuck The Class 工作流中视为只读。
- PDF 工作流遇到未解决页码范围或视觉不确定性时会停止，不会静默补写内容。

