# 结构与规则

## 目录

- 课程目录
- 种子文件
- 各动作必需文件
- 题目锚点
- 链接约定
- 题目隐藏标签
- 试卷元数据
- 解答块
- 做题记录
- 学习事件 JSONL
- 学生状态快照
- 卡点清单
- 标签治理
- 粗掌握状态
- 派生视图
- 输出自检

## 课程目录

每门课使用一个文件夹：

```text
<学科>/
├── 课程口径.md       # 课程层级的范围、重点和排除项
├── 00_原材料/        # 只读课件、扫描件、作业原件
├── 10_题库/          # 题目、标签、S9 折叠解答块的事实来源
│   └── _标签库.md    # 受控题型词表、计数和治理记录
├── 20_知识/          # AI tutor grounding、章节主干、启动讲解和问答种子
├── 30_我的数据/
│   ├── inbox/        # 新手写截图
│   ├── archive/      # 已处理截图
│   ├── 做题记录.md   # append-only 做题简表
│   ├── 学习事件.jsonl # append-only runtime 学习证据
│   └── 卡点清单.md   # 学习对话和错题暴露的待验证卡点
├── 40_派生视图/      # 可重建考频、候选、复盘、冲刺包、状态快照
└── 90_缓存/          # OCR、转换、分析和临时中间产物
```

S0 必须创建完整骨架和种子文件。S1-S10 在缺少前置文件时，只能创建本 workflow 明确允许的动作专用种子文件，并报告创建内容。不要静默初始化无关目录。除 workflow 明确要求且可恢复或已确认，不移动用户已有文件。

## 种子文件

S0 创建这些文件：

```text
课程口径.md
10_题库/_标签库.md
30_我的数据/做题记录.md
30_我的数据/学习事件.jsonl
30_我的数据/卡点清单.md
```

`课程口径.md` 必须通过 `scripts/course_profile.py init` 创建，不手写变体。结构为：

```markdown
# 课程口径

## 学习阶段

未设置

## 已确认教学/考试范围

未设置

## 教师重点与主线/补充关系

未设置

## 明确排除内容

未设置
```

`学习阶段` 是自由文本，只调整解释方式和默认先修，不扩展范围。范围优先级是：当前用户指令、此文件确认范围、用户确认教师重点、课程材料。旧课程缺失该文件时，不隐式创建，使用已提供材料作为边界。题库和标签库可显示重点和命名，但不能单独授权材料外理论。

`10_题库/_标签库.md`：

```markdown
# 标准标签库

> 本文件是本课程题型标签的唯一词表。打标先从这里选；新增、合并、计数都在这里维护。

## 字段规则

- `chapter`:
- `question_type`: 使用 `主类｜子类`，必要时三级。
- `capability_theme`: 每个知识点标签必须且只能属于一个稳定能力主题。

## 标准题型词表

| 章节 | 能力主题 | 标准知识点标签 | 题数 |
|---|---|---|---:|
| 第一章 | 待归并主题 | `待归并标签` | 0 |

## 稀疏标签合并记录

## 维护规则

- 先从现有词表中选，不新造词。
- 新标签必须能覆盖至少 2 题，或语义明显独立且有长期检索价值。
- 新增标签前反查旧卷，确认不是已有标签的改写。
- S1 修改题库后同步更新题数计数。
```

`30_我的数据/做题记录.md`：

```markdown
# 做题记录

| 日期 | 锚点 | 判定 | 错因 | 一句话 | 截图 |
|---|---|---|---|---|---|
```

`30_我的数据/学习事件.jsonl`：

```text
```

空文件合法。它是 S10 runtime 的 append-only 学习证据，不替代完整对话上下文。

`30_我的数据/卡点清单.md`：

```markdown
# 卡点清单

> 本文件连接概念学习和刷题证据。S7 追加学习对话卡点；S5 可追加做题暴露出的概念卡点。卡点是待验证学习证据，不是永久能力标签。
```

`40_派生视图/` 的文件不是种子文件。只有 S2/S4/S5/S6/S10 运行时才创建。

## 各动作必需文件

| Action | 输入文件 | 源文件 | 输出文件 |
|---|---|---|---|
| S0 setup/check | course root、可选学习阶段和范围说明 | 无 | 完整目录树、`课程口径.md`、`_标签库.md`、`做题记录.md`、`学习事件.jsonl`、`卡点清单.md` |
| S1 paper intake | 试卷/PDF/照片/文本，最好在 `00_原材料/`；PDF 需要已验证 `90_缓存/pdf-to-markdown/<stem>/completion.json` | `_标签库.md`；可选 `20_知识/` | `10_题库/<卷名>题面整理.md`、更新 `_标签库.md`、必要 PDF cache |
| S2 frequency analysis | 目标考试或范围 | 全部 `10_题库/*.md`、`_标签库.md`；可选 `做题记录.md`、`卡点清单.md`、`20_知识/` | `考频矩阵.md`、`主题题表.md` |
| S3 attempt evidence intake | `30_我的数据/inbox/*` 截图 | 匹配题库、`做题记录.md`、可选解答块 | 追加 `做题记录.md`、移动图片、可选低解释度 attempt event、可选整卷报告 |
| S4 practice queue | 题目数 `N` | 题库、标签库、`做题记录.md`、`卡点清单.md`、可选 `学习事件.jsonl`、`考频矩阵.md` | `40_派生视图/本轮练习候选.md` |
| S5 mistake review | 可选日期范围 | `做题记录.md`、`学习事件.jsonl`、`卡点清单.md`、题库、可选 `20_知识/`、`课程口径.md` | `复盘报告.md`、可选追加 `卡点清单.md` |
| S6 cram pack | 可选考试范围/时间 | `做题记录.md`、`学习事件.jsonl`、`卡点清单.md`、题库、标签库、可选 S2/S5 视图 | `冲刺包.md`、可选模拟卷 |
| S7 dialogue extraction | 导出对话 `.md`/`.txt` | `卡点清单.md`、`20_知识/`、`_标签库.md` | 追加 `卡点清单.md`、提取摘要 |
| S8 courseware digest | 章节范围、课件映射、主线/补充判断 | 源课件、可选 `课程口径.md`、现有 `20_知识/`、可选标签库和考频 | `20_知识/第XX章_主干重点.md`、同步 README/框架、必要 cache |
| S9 verified solutions | 题目 anchor、可选参考答案 | 匹配题库、可选 `课程口径.md` | 题下折叠解答块、未决清单 |
| S10 tutor session | 用户当前问题/作答/目标 | `课程口径.md`、相关 `20_知识/`、题库、`做题记录.md`、`学习事件.jsonl`、`卡点清单.md`、可选 S2/S4/S5/S6 视图 | 追加 `学习事件.jsonl`、可选 `学生状态快照.md`、可直接执行或按成本委托 S1-S9 |

## 题目锚点

全局唯一锚点：

```text
<年份>-<卷类>-<题号>
```

例：`24-25期中-算7`、`23-24期末-选3`、`章节卷-填2`。每个题库条目应以 anchor 作为标题或包含 anchor，方便练习候选链接到干净题面。

## 链接约定

读者是 Obsidian；vault 根是包含课程文件夹的学习根目录。规则：

- 跨文件链接使用 vault-root-relative wikilink：`[[<course>/10_题库/<file>#<anchor>|label]]`。
- 文内链接使用 `[[#heading]]`。
- 不使用 `[[../...]]` 相对路径 wikilink。
- 隐藏标签使用 Obsidian 注释 `%% %%`。

## 题目隐藏标签

机器可读标签存放在题目附近的 Obsidian 注释块：

```markdown
%%
chapter: 第五章
question_type: 二重积分｜极坐标
source: 2024-2025期中
score: 8
question_form: 计算题
ocr_status: 已对照 PDF 复核
%%
```

必需字段是 `chapter` 和 `question_type`。新 S1 入库还必须写 `question_form` 和 `ocr_status`；旧条目可按兼容规则读取。

`question_form` 闭合词表：

- `选择题`
- `填空题`
- `计算题`
- `证明题`
- `应用题`
- `简答题`
- `综合题`
- `未判定`

旧条目题型形式按顺序解析：显式 `question_form`、anchor 推断（`-选` / `-填` / `-算` / `-证` / `-应`）、`未判定`。不要从分值推断。

`ocr_status` 闭合词表：

- `待复核`: 仍有具体 OCR、图、公式或来源不确定。S4/S9 默认不可消费。
- `已做结构修复`: 未记录已知缺陷，但未逐题对照认证来源。
- `已对照 PDF 复核`: 已对照认证 PDF Markdown 或源 PDF 复核题面。

旧条目缺失 `ocr_status` 时按 `已做结构修复` 读取；不要写回升级，也不要从“看起来干净”推断 `已对照 PDF 复核`。

## 试卷元数据

新 S1 必须在文档首个 H1-H6 附近放置文档级隐藏块：

```markdown
%%
chapter: 综合
question_type: 真题整卷｜期末
source: 2023-2024期末A
paper_type: 期末
academic_year: 2023-2024
%%
```

`paper_type` 使用考试总体名称，如 `期中`、`期末`、`其他`。`academic_year` 使用连续年份 `YYYY-YYYY`；新 S1 若确实未知，显式写 `academic_year: 未知`，不要靠缺字段表达未知。旧文件可从 `source` 推断；兼容推断规则是：`source` 含 `期中` 推为 `期中`，含 `期末` 或 `缺卷头` 推为 `期末`，否则为 `其他`。未知年份只参与总频率，不参与时间趋势。

展示百分比或百分点变化时，把存储小数乘以 100，并用 `ROUND_HALF_UP` 四舍五入为整数；负半值同样远离 0。

## 解答块

S9 核验解答直接写在题目下方的 Obsidian 折叠 callout，默认折叠，保持题面干净：

```markdown
> [!note]- 解答｜状态：已对照一致
> （完整步骤，每步说明理由）
> 起手：一句正确第一步，供 S6 保底清单消费。
```

状态闭合：`已对照一致` / `与参考答案不一致（已裁决）` / `独立解答未对照` / `存疑`。只有 S9 写或更新这些块，不改题面、anchor 或标签。

## 做题记录

`30_我的数据/做题记录.md` 是 append-only：

```markdown
| 日期 | 锚点 | 判定 | 错因 | 一句话 | 截图 |
| 2026-06-11 | 24-25期中-算7 | 错 | 计算错 | 拉格朗日方程组漏解一组 | [[微积分/30_我的数据/archive/20260611_24-25期中-算7_01.png]] |
```

判定闭合：

- `对`
- `对但慢`
- `卡`
- `错`
- `空`

错因闭合：

- `概念错`
- `起手错`
- `计算错`
- `审题错`
- `没思路`

`对` 和 `对但慢` 的错因留空。`对但慢` 必须来自用户自报，不从截图推断。

每个 S3 确认批次追加一个隐藏 marker：

```markdown
<!-- s3-batch:<batch-id> -->
```

对应 `90_缓存/s3-grading/<batch-id>.json` 是恢复来源。重试发现 marker 时必须恢复图片归档，不重复追加记录。

## 学习事件 JSONL

`30_我的数据/学习事件.jsonl` 是 append-only，一行一个 JSON 对象。它记录有意义的学习证据，不记录每句聊天。S3 自发写入时只能写低解释度 attempt event：闭合判定、粗错因、证据坐标、截图/题目引用和低层批改事实；不要写 `diagnosis_hypothesis`、`next_probe`、`tutor_action` 或状态判断，除非这些内容由 S10 已经现场形成并明确要求写入。

推荐最小字段：

```json
{
  "event_id": "20260619-001",
  "time": "2026-06-19T16:40:00+08:00",
  "event_type": "attempt",
  "origin": "s10",
  "created_by": "main_agent",
  "anchor": "24-25期末-算3",
  "student_goal": "练习起手",
  "student_response_summary": "选了反向条件概率",
  "turn_summary": "学生把条件方向写反，提示后能修正第一步",
  "judgement": "错",
  "coarse_wrong_cause": "概念错",
  "diagnosis_hypothesis": "混淆条件概率方向",
  "evidence": "学生把 P(患病|阳性) 写成 P(阳性|患病)",
  "confidence": "high",
  "tutor_action": "contrastive_probe",
  "hint_level": 1,
  "next_probe": "判断三道题分别问哪个条件概率，不计算",
  "next_action_reason": "验证学生是否掌握条件方向，而不是只记住本题",
  "outcome": "repaired_with_hint",
  "source_refs": ["[[课程/10_题库/2024期末#24-25期末-算3]]"]
}
```

字段规则：

- `event_id`、`time`、`event_type`、`origin`、`evidence` 必填。
- `event_type` 闭合：`attempt` / `question` / `explanation` / `probe` / `repair` / `variant` / `reflection` / `state_update`。
- `origin` 闭合：`s3` / `s10` / `manual` / `import`。S3 自发写入时必须是 `s3`，且只能写低解释度 `attempt` event。
- `created_by` 闭合：`main_agent` / `subagent` / `user` / `script`。
- `outcome` 闭合：`not_tested` / `observed` / `repaired_independently` / `repaired_with_hint` / `needs_followup` / `not_repaired` / `deferred`。
- `confidence` 闭合：`low` / `medium` / `high`。
- `judgement` 仅在 `event_type: attempt` 时可写，取值同做题记录判定。
- `coarse_wrong_cause` 仅在 `event_type: attempt` 且需要粗索引时写，取值同做题记录错因。
- `diagnosis_hypothesis` 是开放文本，用于 S10 教学判断；它必须由 `evidence` 支撑，并同时写 `confidence` 和 `next_probe`。S3 不主动生成该字段。
- `next_probe` 写下一步最小验证问题；它由 S10 形成，不由 S3 主动生成。
- `turn_summary` 写本轮学生表现的短摘要；`next_action_reason` 写为什么下一步要这样追问或练习。二者服务未来恢复上下文，不替代完整对话。
- `source_refs` 使用 vault-root-relative wikilink 数组。

## 学生状态快照

`40_派生视图/学生状态快照.md` 是派生文件。文件第一行必须是：

```markdown
> 派生文件，可重新生成，勿手改。
```

内容应只写 evidence-backed claims，例如：

```markdown
## 条件概率｜贝叶斯公式

### 当前判断
学生能识别条件概率题，但条件方向不稳定。

### 证据
- 2026-06-19：24-25期末-算3，把 P(患病|阳性) 写成 P(阳性|患病)。

### 当前最可能误解
把“已知检测阳性后患病概率”理解成“患病时检测阳性概率”。

### 下一步最小验证
只做 3 道条件方向判断题，不做完整计算。
```

状态快照必须能从 `学习事件.jsonl`、`做题记录.md` 和 `卡点清单.md` 重建；不要手工写不可追溯的掌握度真相。

## 卡点清单

`30_我的数据/卡点清单.md` 连接概念学习和刷题证据。S7 追加学习对话卡点；S5 可追加错题暴露的概念卡点。卡点表示待验证假设，不是已定性的能力缺陷。

推荐形状：

```markdown
## 第六章

<!-- s7-item:<source_sha256>:明确疑问:<evidence_lines> -->
- 来源: S7学习对话提取｜类型: 明确疑问｜题型: 共射放大电路｜状态: 待检验
  卡点: 为什么静态工作点和小信号模型要分开看
  概念键: 放大电路｜静态工作点与小信号模型
  证据: 用户明确要求换角度解释同一概念
  evidence_source: <vault-root-relative cached dialogue path>
  evidence_source_sha256: <source file SHA-256>
  evidence_lines: <1-based start>-<1-based end>
  原文摘录:
  > 保留聊天记录中最终讲通的解释原文，不改写。
```

新 S7 条目前必须写 idempotency marker：

```markdown
<!-- s7-item:<source_sha256>:<类型>:<evidence_lines> -->
```

新 S7 条目必须带 `evidence_source`、`evidence_source_sha256`、`evidence_lines`。`最终讲通解释` 还必须带 `quote_source`、`quote_source_sha256`、`quote_lines`、`quote_sha256`，超过 25 行时加 `quote_scope_reason`。

当前 S7 类型闭合：

- `用户提问`
- `明确疑问`
- `被纠正的误解`
- `最终讲通解释`

旧 `追问≥2轮` 记录继续兼容，但新提取不再写。

S7 规则：

- 只抽取当前四类。
- 一个清晰疑问足够成为 `明确疑问`。
- “继续”“下一页”“开始这节”等进度话术不算卡点，除非伴随真实疑问。
- `最终讲通解释` 必须对应前面的 `用户提问` 或 `明确疑问`。
- 跳过仅重复 `20_知识/` 的材料。
- `question_type` 只在匹配 `_标签库.md` 时写；否则留空或 `未映射`。
- `概念键` 是稳定短路径，不修改 `_标签库.md`。
- 对话导出在 vault 或课程树外时，逐字节复制到 `<course-root>/90_缓存/s7-dialogue/`，并使用缓存路径。
- 最终解释摘录逐字保留，不润色、不翻译、不修正。

S4 和 S5 消费此文件：

- S4 提高未练习卡点相关题型的候选优先级。
- S5 把同时出现在概念卡点和 `概念错` 中的题型标为 `确认顽固弱点`。

## 标签治理

题型标签使用 `主类｜子类`，只有长期检索价值明确时才用第三级。

规则：

- 先从 `_标签库.md` 选择。
- 每个受控知识标签都必须映射且只映射到一个 `capability_theme`。
- 不为一次性表述差异新造标签。
- 新标签至少覆盖 2 题，或语义独立且有长期检索价值。
- 新增前反查旧卷，确认不是已有标签改写。
- 区分不会改变练习决策时，优先向上合并稀疏变体。
- S1 修改题库时同步更新 `_标签库.md` 计数和能力主题映射。
- S2 消费该映射，不发明也不修复。

## 粗掌握状态

从 `做题记录.md` 按题型派生掌握状态，不另存源文件。

- `未接触`: 无记录。
- `红`: 最新尝试是 `错` 或 `空`。
- `黄`: 最新尝试是 `卡` 或 `对但慢`，或红后第一次 `对`。
- `绿`: 不同日期连续两次 `对`。

任何 `错` 或 `空` 都立即回到 `红`。该状态只做粗视图，不替代 S10 的开放诊断假设。它只用于 S4/S5 的候选筛选和复盘视图；S10 不默认把红黄绿直接说给学生听，除非用户明确要求查看统计状态。

## 派生视图

`40_派生视图/` 中每个 Markdown 文件第一行必须是：

```markdown
> 派生文件，可重新生成，勿手改。
```

派生文件从源数据整体重建。除非用户明确要求并理解其派生性质，不手改单个计数、队列项或行。

## 输出自检

任何写课程产物的 workflow 在报告完成前必须运行：

```text
python <skill>/scripts/validate_course_artifacts.py --course-root <course-root> --scope <s1|s2|s3|s4|s5|s6|s7|s8|s9|s10|all>
```

退出码：`0` 通过，`2` 有产物问题必须修复，`3` 课程或 scope 无效。S2 还会校验分析输入 fingerprint 和 JSON 到 Markdown 的 byte-for-byte 渲染。

校验内容：

1. 控制字符：文件不能含不可见控制字符。LaTeX 反斜杠可能被 shell 吞掉，必须用正则扫描。
2. LaTeX 损坏模式：无反斜杠的 `qquad/quad/frac/left/right`，`\left` 与 `\right` 配对，`$`/`$$` 平衡。
3. 链接：文内和跨文件链接必须存在。
4. 派生标记：`40_派生视图/` Markdown 必须有派生文件标记。
5. S7 证据：marker、hash、行号、逐字引用必须一致。
6. S10 学习事件：JSONL 必须逐行合法，`event_id` 不重复，`time` 是 ISO 8601，闭合字段取值正确，`source_refs` wikilink 可解析，非 attempt 事件不得写 `judgement` 或 `coarse_wrong_cause`。
7. 根因预防：反斜杠密集内容通过文件写入工具写入，不用 shell 字符串插值。
