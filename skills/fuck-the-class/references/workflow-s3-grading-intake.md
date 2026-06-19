# S3 作答证据入库

目的：处理 `30_我的数据/inbox/` 中的离线手写截图，把它们变成可追溯作答证据。S3 是证据管理员，不是教学诊断模块。

## 输入

- inbox 图片
- 模式：默认 `日常`，用户要求时用 `整卷`

## 必需文件

- 读取：`30_我的数据/inbox/*`
- 读取：`10_题库/` 下匹配题目文件
- 读写：`30_我的数据/做题记录.md`
- 可选追加：`30_我的数据/学习事件.jsonl`
- 写入/移动：`30_我的数据/archive/`
- 可选写入：`40_派生视图/整卷失分统计.md`

## 步骤

1. 分配稳定 `batch-id`，在入库前用每张 inbox 图片运行 `s3_batch_gate.py prepare`。若 batch 文件已存在，读取其状态并恢复，不创建第二个 batch。
2. 只读取截图到足以识别手写 anchor、确认作答结果和维护证据的程度。不要长篇转写手写过程。
3. anchor 不清楚时列出图片并询问用户，不猜。
4. 对照题目确认闭合作答结果；若题下有折叠解答块，用它作参考，优先使用 `已对照一致` 或 `与参考答案不一致（已裁决）`。没有解答块时可直接解题判分，解答不是 S3 的硬依赖。
5. 错或卡时，只记录低层批改事实，例如“与参考解答第 2 步不一致”“第一步未写出目标公式”“结果数值与标准答案不同”。不要生成开放诊断假设、教学解释、`next_probe` 或学生状态判断。
6. 用固定判定和错因词表提出每次尝试的一行追加记录。`一句话` 列写低层事实，不写“学生因为……不会”的教学诊断。
7. 写入前请求一次批次确认，并明确询问哪些正确尝试是 `对但慢`。`对但慢` 只接受用户自报，不从截图推断。
8. 确认后，在同一次写入中追加记录行和一个 `<!-- s3-batch:<batch-id> -->` marker，然后运行 `mark-recorded`。重试时若已看到 marker，跳过追加。
9. 必要时追加低解释度 `attempt` 学习事件。S3 自发写入的 event 必须写 `origin: "s3"`，只允许包含 `event_id`、`time`、`event_type: attempt`、`origin`、`anchor`、`judgement`、`coarse_wrong_cause`、`evidence`、`confidence`、`source_refs`、`student_response_summary` 等证据字段；不得主动写 `diagnosis_hypothesis`、`next_probe`、`tutor_action` 或状态判断。
10. 若 S10 已经在主线程完成诊断，并明确要求把某个 `diagnosis_hypothesis` 或 `next_probe` 写入学习事件，S3 可以按 S10 给出的内容代写；不要自行补全。
11. 把每张图重命名为 `YYYYMMDD_锚点_序号.<原扩展名>`，移动到 `archive/`，每次成功移动后运行 `mark-moved`。全部归档后运行 `finalize` 和 `verify`。
12. `整卷` 模式下，可额外重建 `40_派生视图/` 中的得分/失分拆解；该报告只呈现分数和题目层证据，不做教学诊断。
13. 报告完成前运行 `python <skill>/scripts/validate_course_artifacts.py --course-root <course-root> --scope s3`；若写入了学习事件，再运行 `python <skill>/scripts/validate_course_artifacts.py --course-root <course-root> --scope s10`。

## 输出

- 追加的做题记录
- 归档后的截图证据
- 可选低解释度 attempt 学习事件
- 可选整卷失分报告

## 边界

当前聊天中的作答由 S10 main agent 直接理解、诊断和教学；S3 只处理离线 inbox、批量截图、整卷截图和归档维护。S3 可以判分和归档，但不生成教学诊断、`next_probe` 或状态快照。开放诊断假设只能由 S10 在主线程上下文中形成，或由 S10 明确指示 S3 写入。
