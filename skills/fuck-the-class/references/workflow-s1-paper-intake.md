# S1 试卷入库

目的：把试卷、作业、扫描件、照片批次或已有文本整理成带标签的题库文件；也支持对已入库题目做知识标签精标回填。

## 输入

- 源文件或截图
- 课程根目录
- 模式：`入库` 默认，或 `精标回填`
- 可选 anchor 命名约定
- 可选种子词表：同课程旧项目的已验证标签库，或 `20_知识/` 章节笔记末尾的 `未对齐题型名`

## 必需文件

- 读取：源文件，最好放在 `00_原材料/`
- 读写：`10_题库/_标签库.md`
- 可选读取：`20_知识/` 用于章节映射和 `未对齐题型名`
- 写入：`10_题库/<卷名>题面整理.md`
- 每个 PDF，包括扫描 PDF，都需要已验证 cache：`90_缓存/pdf-to-markdown/<source-stem>/completion.json`

## 步骤

1. 若源文件是 PDF，包括扫描 PDF，严格执行 `pdf-ingestion.md` 的 Gate 0 和 Gate 1。只有当前源文件、认证 Markdown、已验证分段、页覆盖和零 unresolved items 全部通过独立 completion verifier 后才能继续。不要消费 draft、独立中间分段或自然语言成功声明。独立照片可直接读图，并保留视觉不确定性等待确认。
2. 若是 PDF 入库，写入前检查 `90_缓存/s1-intake/*/intake.json` 是否已有相同源 SHA-256。完整绑定表示源文件已入库，停止而不是创建重复 anchor。照片、截图或已有文本入库暂不要求 s1-intake manifest；需要去重时，把源文件 hash 写入轻量 source ledger 或在本次报告中列明。
3. 冷启动时，如果 `_标签库.md` 为空或没有知识层标签，先建词表再打标。优先导入用户给的种子词表；没有种子时，从 `20_知识/` 的 `未对齐题型名` 或课件目录草拟初始知识层词表。不要因为词表空就把所有题丢进 `选择题｜待精标` 之类形式占位。占位标签只用于确实无法判断的个别题，并报告数量和后续解决动作。
4. 把合并扫描包拆成不同试卷，再把每份试卷拆成单题；S1 不解题。
5. 按课程约定分配 anchor。
6. 用 Markdown 和 LaTeX 写干净题面。
7. 写文档级 `paper_type`、`academic_year`；写题目级 `chapter`、`question_type`、`question_form`、`ocr_status`。具体来源不确定时用 `待复核`；只有对照认证来源后才能用 `已对照 PDF 复核`；其余用 `已做结构修复`。
8. 从 `_标签库.md` 选择 `question_type`，并使用已有 capability-theme 映射。没有合适标签时按标签治理新增，且同一操作内给新标签分配唯一 capability theme。
9. 更新 `_标签库.md` 计数，并确认每个受控标签都有唯一 capability theme。
10. `精标回填` 模式：不改题面、anchor 和解答块；只替换占位/未判定知识标签、按请求补缺失 `question_form`、在有事实证据时修复试卷元数据、补全 `_标签库.md` 的 capability-theme 映射。不要批量升级旧 OCR 状态。
11. 运行 `python <skill>/scripts/validate_course_artifacts.py --course-root <course-root> --scope s1`。
12. PDF 入库时，用准确源 PDF、completion.json、每个输出试卷和 `$pdf-to-markdown` skill 路径运行 `s1_intake_gate.py bind`，再运行 `s1_intake_gate.py verify`。二者未通过前 S1 不完成。
13. 报告题型形式完整度、OCR 状态计数、capability-theme 映射完整度和 intake manifest 路径。提醒用户源数据变化后需要重新生成 S2。

## 输出

- `10_题库/<卷名>题面整理.md`，严格一份试卷一个文件；合并扫描包必须拆成多份试卷文件
- 标签库变更摘要
- 试卷元数据、题型形式完整度、capability-theme 映射摘要

## 边界

PDF completion gate 通过前，不拆题、不改 `_标签库.md`、不创建或更新 `10_题库/`。转换子代理运行时，S1 parent 不写子代理拥有的转换产物，不替子代理 finalize。S1 parent 永远不创建或修复 `completion.json`。唯一可消费的 PDF 文本是 certificate 当前 `final_markdown`；禁止消费 `draft.md`、`.mineru.md`、`source/`、`repaired/`。S1 不写答案或解析；需要解答时转 S9。
