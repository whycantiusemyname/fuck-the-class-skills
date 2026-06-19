# Fuck The Class Skills

面向大学课程的 Codex 技能包：把课程材料、PDF、课件、真题、作业、做题截图、学习对话和错题记录整理成一套可追溯的本地应试学习系统。

这个项目的核心不是手写一套传统 ITS 决策树，而是给强模型提供可靠的课程证据层。模型在主线程保留完整对话上下文，现场判断该讲、该问、该让学生试一步，还是该调用后台文件动作。

## 包含技能

- [`fuck-the-class`](skills/fuck-the-class/)：课程整理、题库入库、考频趋势、练习候选、批改证据、错因复盘、课件消化、核验解答、冲刺包和 S10 主线程 AI 私教 runtime。
- [`pdf-to-markdown`](skills/pdf-to-markdown/)：把 PDF 转成经过分段修复、视觉核对和 completion certificate 约束的 Obsidian Markdown，供题库和课件消化安全消费。

## 设计原则

- **证据层，不是手工学生模型**：题库、考频、做题记录、学习事件、卡点和状态快照服务于恢复、审计、委托和跨轮延续，不替代主线程对当前学生的理解。
- **主线程优先**：S0 初始化后默认进入 S10。学生当前问题、犹豫、作答和提示后的修正，优先保留在 main agent 的自然上下文里。
- **后台动作有边界**：S1-S9 是可委托、可验证的文件动作。大 PDF/OCR、全量入库、考频分析、批量截图和大范围配解答适合后台；当前教学和小范围读写通常由 main agent 直接完成。
- **候选，不是日程**：S4 生成 `本轮练习候选.md`，帮助 S10 选题和解释推荐理由；它不替用户安排每日计划。
- **应试但不压扁理解**：输出围绕考点、题目信号、第一步、公式条件和常见错误，但不会为了短而删掉必要推理桥、例子或先修解释。

## Fuck The Class 能做什么

### S0 课程初始化

创建或审计课程文件夹，生成：

- `00_原材料/`
- `10_题库/`
- `20_知识/`
- `30_我的数据/`
- `40_派生视图/`
- `90_缓存/`
- `课程口径.md`
- `学习事件.jsonl`

初始化后，默认进入 S10 主线程私教姿态。

### S1 试卷入库

把 PDF、扫描件、照片批次、作业或已有文本整理成题库。新入库题目会记录：

- 试卷类型和学年
- 章节和受控知识标签
- 题型形式
- OCR/来源复核状态
- 题目 anchor 和原始来源

PDF 入库必须通过 `pdf-to-markdown` 的 completion gate，并绑定 `s1-intake` manifest。

### S2 考频与趋势

确定性生成考频缓存和两个派生视图：

- `考频矩阵.md`
- `主题题表.md`

趋势中的“覆盖”指年度覆盖；分值展示区分近期累计已知分值和必要时的每卷平均已知分值。

### S3 作答证据入库

处理 `30_我的数据/inbox/` 的离线手写截图，追加做题记录、归档图片，并可写低解释度 attempt event。

S3 不生成开放诊断假设，不写 `next_probe`，不替代 S10 的现场教学判断。

### S4 本轮练习候选

根据题库、考频、做题记录、卡点和学习事件，生成当前 session 可用的真实题候选上下文。

它给 main agent 推荐理由和替代路径，不决定用户一天要学多少。

### S5 错因复盘

汇总粗错因，同时保留开放诊断假设、证据链、反证和下一步验证。S5 可以追加卡点，但必须使用 idempotency marker，避免重复沉淀同义问题。

### S6 冲刺包

生成考前保底清单、起手训练和提醒卡。默认只重组真实题；如果用户明确要求生成变式题，必须标注来源题、测试能力和“非原始真题”。

### S7 学习对话提取

从导出的 AI 学习对话中提取真正暴露卡点的内容。最终讲通解释按原文逐字保留，不润色、不压缩。

### S8 课件消化

把章节课件整理成 AI tutor grounding 和学生可读的章节主干：

- 这一章抓什么
- 阅读层次表
- 整体直觉
- 分节主干
- 主动问答种子
- 条件、坑点、反例和题型信号

S8 不应被写成超短提纲或高密度压缩文档；S10 增量内容只能作为 guided review 契约的补充。

### S9 核验解答

把已核验解答写到题目下方的折叠块。起手句可被 S6 消费；存疑题不会被当成可靠起手来源。

### S10 主线程 AI 私教

S10 是默认运行时：

- 用完整对话上下文理解学生
- 根据课程证据主动 probe
- 围绕作答错误进行系统问答
- 讲完后制造 repair action
- 只在有跨轮保留价值时写学习事件
- 可重建 `学生状态快照.md`

学习事件使用轻字段，例如 `origin`、`turn_summary`、`outcome`、`next_action_reason` 和 `created_by`。它们用于恢复教学现场，不是手写复杂学生模型。

## PDF 转 Markdown

`pdf-to-markdown` 可以单独使用，也可以作为 S1/S8 的 PDF 入口。它支持：

- MinerU 解析
- 分段 LLM 修复
- Obsidian Markdown 规范化
- 逐页视觉核对
- completion certificate 校验
- 未决问题阻断交付

下游技能只消费已完成并通过验证的 Markdown，不消费 draft 或中间产物。

## 安装

把技能目录复制到 Codex 技能目录：

```powershell
$skillsHome = Join-Path $HOME ".codex\skills"
Copy-Item -Recurse -Force .\skills\fuck-the-class $skillsHome
Copy-Item -Recurse -Force .\skills\pdf-to-markdown $skillsHome
```

PDF 转换依赖 Python 3.10+：

```powershell
python -m pip install -r requirements-pdf.txt
```

使用 MinerU 前，设置 `MINERU_API_TOKEN`。

## 校验

校验技能结构：

```powershell
python "$HOME\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .\skills\fuck-the-class
```

运行测试：

```powershell
python -m unittest discover -s .\skills\fuck-the-class\tests
python -m unittest discover -s .\skills\pdf-to-markdown\tests
```

课程产物校验由技能内脚本执行：

```powershell
python .\skills\fuck-the-class\scripts\validate_course_artifacts.py --course-root <course-root> --scope <s1|s2|s3|s4|s5|s6|s7|s8|s9|s10|all>
```

## 项目结构

```text
skills/
  fuck-the-class/
    SKILL.md
    agents/openai.yaml
    references/
    scripts/
    tests/
  pdf-to-markdown/
    SKILL.md
    agents/openai.yaml
    references/
    scripts/
    tests/
requirements-pdf.txt
```

## 使用示例

```text
使用 $fuck-the-class 初始化这门课程。
```

```text
使用 $fuck-the-class 把这些历年试卷整理进题库，并生成考频趋势。
```

```text
使用 $fuck-the-class 根据我刚才的作答进行 S10 私教复盘。
```

```text
使用 $fuck-the-class 消化这一章课件，然后先按主干讲一轮并主动问我一个高概率卡点。
```

```text
使用 $pdf-to-markdown 把这份 PDF 转成经过核对的 Obsidian Markdown。
```
