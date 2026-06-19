---
name: fuck-the-class
description: "面向大学课程的应试冲刺与 AI 私教记忆层：把课程文件夹、PDF、扫描件、作业、截图、做题记录、学习对话、题库、标签、错题、参考答案整理成可追溯的题库、核验解答、考频趋势、练习候选、批改记录、卡点证据、复盘、冲刺包和 S10 主线程私教 runtime，不扩展出已确认课程范围。用户提到 Fuck The Class、应试冲刺、快速理解课程、新学科初始化、课程文件夹整理、试卷入库、题型分类、考频分析、趋势预警、近期热点、题型变化、考法迁移、批改截图、学习对话提取、卡点清单、课件梳理、章节梳理、配解答、核验解答、出题队列、错因复盘、冲刺包、AI 私教、tutor session 或 source-bound tutoring 时使用。"
---

# Fuck The Class

## 总览

使用本技能时，把它当成一个 **source-bound AI tutoring memory layer**：它保存课程材料、考试边界、题库坐标、考频证据、学生作答、学习事件和可重建状态；具体教学判断由主线程强模型在运行时完成。

本技能服务本科和研究生课程。它假设每门课有一个受控本地文件夹：原材料、题库、知识 grounding、个人数据、派生视图和缓存分开保存，保证后续任务有单一事实来源。

S0 初始化后，默认进入 S10 主线程私教 runtime。S10 不是传统 ITS 决策树，而是主线程对话外壳：main agent 保留完整学生对话上下文，按证据即时选择讲解、追问、提示、变式、练习、直接执行文件动作或委托后台动作。

## 每次任务开始

1. 确认课程根目录。若用户未给出，只有当前 workspace 能唯一指向一门课时才自动推断；否则询问课程文件夹和目标动作。
2. 识别动作：
   - S0 课程初始化/检查：创建或审计课程骨架和种子文件；完成后进入 S10 姿态。
   - S1 试卷入库：把试卷、作业、PDF、扫描件、照片或已有文本写入 `10_题库/`。
   - S2 考频分析：从题库确定性重建重要性、时间趋势、题型变化和主题题表。
   - S3 作答证据入库：处理 `30_我的数据/inbox/` 的离线手写截图，维护证据坐标、判定简表和归档状态。
   - S4 练习候选：生成当前 session 可用的候选上下文和 main agent 推荐。
   - S5 错因复盘：汇总粗错因，并形成开放诊断假设与下一步验证。
   - S6 冲刺包：生成考前保底清单、起手训练和提醒卡。
   - S7 学习对话提取：从导出的 AI 学习对话中抽取概念阶段卡点证据。
   - S8 课件消化：把章节课件转成 AI tutor grounding、学生启动入口、主干讲解和主动问答种子。
   - S9 核验解答：在题库题目下加入已核验折叠解答块。
   - S10 私教会话：运行主线程 tutoring runtime，利用证据层自然互动、主动追问、沉淀学习事件和状态快照。
   - setup/check：S0 的别名。
3. 写入或校验任何课程产物前，先读 [references/schema-and-rules.md](./references/schema-and-rules.md)。
4. 若存在 `<course-root>/课程口径.md`，必须读取。范围和讲解口径按以下优先级执行：当前用户指令、已确认教学/考试范围、用户确认的教师重点、课程材料。`学习阶段` 只调整解释方式和默认先修，不扩展课程边界。若缺失，兼容旧课程并以已提供材料为边界。
5. 只读取选中动作对应的 workflow；用户明确要求组合操作时才读取多个：
   - S0: [workflow-s0-course-setup.md](./references/workflow-s0-course-setup.md)
   - S1: [workflow-s1-paper-intake.md](./references/workflow-s1-paper-intake.md)
   - S2: [workflow-s2-frequency-analysis.md](./references/workflow-s2-frequency-analysis.md)
   - S3: [workflow-s3-grading-intake.md](./references/workflow-s3-grading-intake.md)
   - S4: [workflow-s4-practice-queue.md](./references/workflow-s4-practice-queue.md)
   - S5: [workflow-s5-mistake-review.md](./references/workflow-s5-mistake-review.md)
   - S6: [workflow-s6-cram-pack.md](./references/workflow-s6-cram-pack.md)
   - S7: [workflow-s7-dialogue-extraction.md](./references/workflow-s7-dialogue-extraction.md)
   - S8: [workflow-s8-courseware-digest.md](./references/workflow-s8-courseware-digest.md)
   - S9: [workflow-s9-verified-solutions.md](./references/workflow-s9-verified-solutions.md)
   - S10: [workflow-s10-tutor-session.md](./references/workflow-s10-tutor-session.md)
6. 涉及 PDF、PPT/PPTX、扫描件或 PDF 转换 Markdown 时，读取 [references/pdf-ingestion.md](./references/pdf-ingestion.md)。

## Main Agent 与 Subagent 使用原则

- main agent 是 S10 runtime。它保留学生的自然对话、语气、犹豫、刚才的作答和即时上下文；这些完整上下文优先于结构化摘要。
- 结构化证据层用于恢复、审计、委托和跨轮次延续，不替代 main agent 对当前学生的理解。
- S1-S9 是有边界动作，不默认外包。main agent 可以直接执行，也可以在上下文成本高时委托给 subagent。
- 只有任务耗时长、文件重、会污染当前教学上下文、可独立验收，或已有 manifest/validator 明确 gate 时，才考虑委托。例如大 PDF/OCR、全量入库、全量考频、大课件消化、批量整卷截图、大范围配解答。
- 小范围文件动作通常由 main agent 直接做。例如一两道题的 S9、少量 S3 证据入库、小规模 S4 候选、小复盘、读一两个相关文件。
- 委托时要求 subagent 返回变更文件、校验结果、manifest 状态和不确定项；main agent 负责把结果接回当前教学对话。
- 现场教学默认由 main agent 负责，不把学生当前问题直接甩给 subagent。subagent 不应直接教学生，除非用户明确要求。

## S10 Runtime 原则

- 不等待学生会提出高质量问题。若学生不知道问什么，基于章节主干、常见误区、过往证据或当前题目主动抛出一个最小 probe，例如“如果你不知道问什么，先问自己：这题的已知条件在竖线哪边？”
- 主题文档先建立主干，AI 按主干讲一轮，然后通过练习、追问或小反例暴露真实错误。
- 围绕暴露出的错误进行系统问答，最后沉淀为条件、坑点、反例、题型信号和第一步。
- 没有作答证据时，优先制造一个很小的证据点；用户明确要求直接解释时可以先讲，但讲完要安排 repair action：复述、判断第一步、做近变式或指出易混点。
- 诊断永远是 evidence-backed hypothesis，不是给学生贴永久标签。
- `judgement` 只作为 attempt 类学习事件的可选粗结果，和 `做题记录.md` 的 `对/对但慢/卡/错/空` 对齐；教学主体使用 `diagnosis_hypothesis`、`evidence`、`confidence`、`next_probe`。
- 有意义的学习证据出现后，追加 `30_我的数据/学习事件.jsonl`。不要记录每个闲聊回合。
- `40_派生视图/学生状态快照.md` 是可由学习事件、做题记录和卡点清单重建的派生摘要，不是手工真相。

## 不可违背项

- 用户控制节奏。除非用户要求，不创建日程、每日计划或“明天做什么”。
- 保持单一事实来源：题目、标签和折叠解答块在 `10_题库/`；做题记录在 `30_我的数据/做题记录.md`；学习事件在 `30_我的数据/学习事件.jsonl`；派生视图在 `40_派生视图/`。
- `00_原材料/` 只读。
- 学习和复盘产物必须应试、易懂、绑定课程语言。解释围绕考点、识别信号、第一步、公式条件和常见错误展开；不要为了短而删掉必要先修、推理桥、例子或公式条件。
- 保持课程边界。不要引入源材料和已确认范围以外的理论、记号、证明工具或术语。普通语言类比可以解释已在范围内的内容，但不能新增可考内容。
- 不把手写作业长篇转写成文字。截图是证据文件；S3 文本记录只保存证据坐标、闭合判定、粗错因、低层批改事实和截图链接；开放诊断、`next_probe` 和学生状态判断只能由 S10 形成或由 S10 明确指示写入。
- 闭合词表只用于统计和兼容记录。不要在执行中发明 judgement、wrong-cause 或 question-type 标签；确需新题型标签时按标签治理执行。
- `40_派生视图/` 每个文件都以 `> 派生文件，可重新生成，勿手改。` 开头，并整体重建，不手改局部计数或行。
- S1-S10 写入前检查该动作必需文件。若课程未初始化，先跑 S0，或只创建 schema 允许的动作专用种子文件并报告。
- 遵守写入边界：S1 拥有题面、anchor 和标签；S9 只写题下折叠解答块；S3 只维护离线作答证据层，追加做题记录、归档 inbox 图片，并可写低解释度 attempt event；S5/S7 可追加卡点；S8 写 `20_知识/`；S2/S4/S5/S6/S10 写派生输出或学习事件，其余读取源数据。
- S2 必须运行 `scripts/analyze_frequency_trends.py` 和 `scripts/render_frequency_views.py`，并验证 input fingerprint 和 Markdown 渲染一致性。不要临场重算解析、分类、时间窗或趋势阈值。
- S7 的最终讲通解释必须逐字保留，不润色、不转述、不压缩。
- 不操控用户打开的 Office 或 PowerPoint 窗口；需要时用副本、缓存转换或 headless 工具。
- 证据不确定时说清楚，把不确定项留出确认，不写入不可逆记录。
- 文件写入动作完成前，运行 `python <skill>/scripts/validate_course_artifacts.py --course-root <course-root> --scope <s1|...|s10|all>` 并报告一行自检结果。自然语言扫描不能替代 gate。
- Workflow manifest 是完成证据：S1 PDF 入库需要已验证 `s1-intake` manifest，S3 需要完整批改 batch，S8 需要当前 digest manifest。

## PDF 依赖

S1 和基于 PDF 的 S8 必须以 [references/pdf-ingestion.md](./references/pdf-ingestion.md) 为权威转换和子代理协调契约。不要重述、削弱或临场改写 gate。转换子代理运行时，父级对该 cache 保持只读，并按 Gate 0 等待或交接。只有子代理最终完成且 Gate 1 独立验证 completion certificate 后，才能消费转换 Markdown。没有子代理时，父级可执行同一转换流程，但不能降低任何 gate。不要消费 draft，不要静默进入 fallback skill。

## 输出风格

输出保持操作性：

- 变更文件
- 闭合词表做出的判定
- 需要用户确认的事项
- 未解决的不确定性

避免装饰性 dashboard、泛泛学习建议、不会改变用户下一步行为的分析。

## 常见组合

- 新学科：S0，然后把原始材料放入 `00_原材料/`，后续默认在 S10 里自然互动。
- 概念学习：S8 先消化章节，main agent 用 S10 按主干讲一轮并主动 probe，章节学完后导出对话跑 S7。
- 试卷搭建：S1 入库真题，S2 考频分析，定时整卷后用 S3 做离线作答证据入库，再由 S10 现场复盘。
- 日常练习：S4 给候选上下文，S10 选择本轮任务；当前聊天作答由 S10 直接处理，需要归档离线截图时再交给 S3。
- 诊断：S5。
- 考前：S6。
