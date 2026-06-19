# PDF 入库与转换

当 S1 或 S8 接收 PDF，包括扫描 PDF、需要转 PDF 的 PPT/PPTX 或文档、或 PDF 产出的 Markdown 时，使用本参考。独立照片批次仍是 S1 直接输入，除非先合并成 PDF。

## PPT/PPTX 课件（S8）

先用 headless LibreOffice 和独立 profile 把课件转 PDF，所有转换产物放在 `90_缓存/课件转换/<deck-stem>/`。不要打开或操控用户交互式 Office/WPS 窗口。需要抽取文本时继续走下方 PDF 路径，并保持页码与原课件一致，方便 `见 <课件名> 第N页` 指针有效。

## 必需转换契约

S1 优先启动一个子代理执行 `$pdf-to-markdown`。它拥有：

- preflight 和分块
- MinerU 精确解析
- 上传和轮询
- 结果下载
- 轻量 Obsidian 规范化
- 分段 LLM 通读修复
- 逐页视觉源文核验
- 确定性 finalization 和 `completion.json`

这个所有权持续到子代理达到最终状态，或被明确停止并交接。运行期间，父级可以检查进度，但不能写子代理拥有的转换产物。

中间工作放在课程 cache，例如：

```text
90_缓存/pdf-to-markdown/<source-stem>/
```

传入准确绝对路径源 PDF、cache 目录、请求的最终 Markdown 路径和 `$pdf-to-markdown` skill 路径。要求子代理成功运行 `verify_completion.py` 后才报告完成。若无子代理，父级可执行同一流程，但所有 completion gate 仍强制。

建议子代理任务：

```text
Use $pdf-to-markdown to convert the exact source PDF below.
Complete MinerU preparation, every segmented text repair, page-by-page visual source verification, finalization, and completion verification.
Write all intermediate artifacts under the exact cache directory and write the certified Markdown only to the requested final path.
After finishing each visual-review segment, immediately write both reports/visual_review/verified/segment-XXX.md and reports/visual_review/reviews/segment-XXX.json before starting the next segment. Write unchanged segments too. Do not hold several completed segments in memory for a later batch write.
Do not stop after MinerU or after generating prompts. Do not call any fallback, reconstruction, or vision-crop skill.
Return success only after verify_completion.py exits 0.

Source PDF: <absolute path>
Cache directory: <absolute path>
Requested final Markdown: <absolute path>
Skill: <absolute path to pdf-to-markdown/SKILL.md>
```

S8 可在有用时同样委托，但必须通过同一 certificate gate 后才把转换 Markdown 当作课件来源。

## 规则

- 不把 `$pdf-to-markdown` 脚本复制或改写进本技能。
- 不在此转换路径中使用 legacy visual fallback、visual reconstruction 或 `$pdf-to-obsidian-notes-vision-crop-with-subagent`。
- 不因为扫描件看起来困难就默认启用 OCR；让 PDF 转换流程依据证据决定。
- completion 数据缺失、无效、不完整、不匹配、blocked 或 unresolved 都会使 gate 失败。停止入库并报告准确 blocker，不启动 fallback。
- 原始源文件保留在 `00_原材料/`；清理后的题库只写 `10_题库/`。
- 除非用户要求检查，否则转换产物不进入用户复习界面。
- 保留 `verify_completion.py` 需要的转换证据。cache 中存在某文件不代表可消费；S1/S8 只能在 verification 后消费当前 `completion.json.final_markdown`。无关工具 cache 属于其他所有者，确认无活动 workflow 引用后才可移除。
- S1 永远不创建、patch 或重新解释 `completion.json`。只有 `$pdf-to-markdown` finalizer 写它。
- 短 wait timeout、缺少最终输出或长时间逐页阅读，不等于转换失败。必须使用下面的协调 gate。

## Gate 0：子代理进度、等待和交接

当子代理执行 `$pdf-to-markdown` 时，先应用本 gate，再看 conversion certificate。

### 子代理 checkpoint 规则

每个 manifest segment 完成视觉核验后，子代理必须立即写：

```text
reports/visual_review/verified/segment-XXX.md
reports/visual_review/reviews/segment-XXX.json
```

review JSON 是分段 checkpoint：记录 run id、已审页、hash、变更、unresolved items、状态和 review 时间。没有修正的 segment 也必须产出两个文件。只有两者存在且非空，才能开始下一个 segment。不要把多个已完成 segment 攒到最后批量写。

### 父级等待规则

子代理状态为 `running` 时：

1. 父级对转换 cache 保持只读。不要写 `verified/`、`reviews/`、`workflow_state.json`、最终 Markdown 或 `completion.json`；不要 finalize。
2. 逐页 review 的等待以分钟为单位。10 秒 timeout 只当状态探针，不能成为接管理由。
3. wait timeout 后，检查子代理状态和 checkpoint 数量。用 `probe_pdf_progress.py snapshot` 前后取样，并用 `probe_pdf_progress.py compare`；单纯时间戳变化不算实质进展。若状态、已完成 segment 或已审页覆盖增加，继续等待。
4. 若两者都未进展，发送一次简短状态请求，再等待第二个多分钟间隔。
5. 只有连续两次无进展且无实质子代理响应，父级才可请求 interrupt 或 close。若无法确认子代理已停止，报告转换 blocked，不并发写入。

父级等待时可做无关只读工作，但不能开始 S1 结构化工作或使用未认证转换内容。

### 交接规则

父级只能在以下情况成为转换执行者：

- 从开始就没有可用子代理；
- 子代理达到最终 failed/interrupted 状态；
- interrupt/closure 已确认，父级明确从最后完整 segment checkpoint 恢复。

交接时保留已完成 segment checkpoint，检查最后 review 记录，从第一个未完成 segment 继续。没有源文依据，不重做或覆盖已完成子代理工作。交接后，父级仍必须完成同一 `$pdf-to-markdown` gate 后，S1 才能消费结果。

子代理成功后，等待其最终 agent 状态，再运行独立 completion verifier。自然语言进度或成功消息不能替代磁盘 certificate。

progress probe 只是只读证据。它不授予所有权，不 finalize 子 workflow，也不缩短两轮等待规则。

## Gate 1：转换证书

读取转换 Markdown 前运行：

```powershell
python <pdf-to-markdown-skill>\scripts\verify_completion.py --work-dir <cache-directory>
```

verifier 必须确认：

- `completion.json.status` 是 `complete`
- 源 PDF 和最终 Markdown SHA-256 匹配当前文件
- 最终 Markdown 是当前 verified segments 的有序合并
- 每个视觉 review 通过且 unresolved items 为 0
- 记录的页覆盖包含每一页源 PDF

任何 verifier 失败都会让 S1 在写题库前停止。

## Gate 2：S1 结构

写 `10_题库/` 前检查：

- 每题有稳定 anchor
- 对题目有意义的图被保留或链接
- 公式能以 Markdown/LaTeX 渲染
- `chapter` 和 `question_type` 来自 `_标签库.md`
- 不确定 OCR 或图识别明确标出等待用户确认
