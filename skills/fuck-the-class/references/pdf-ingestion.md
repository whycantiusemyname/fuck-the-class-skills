# PDF 入库与转换

当 S1 或 S8 接收 PDF、扫描 PDF、需要转 PDF 的 PPT/PPTX/文档，或准备消费 PDF 产出的 Markdown 时，使用本参考。独立照片批次仍是 S1 直接输入，除非先合并成 PDF。

## 关键现实约束

- 本流程依赖 companion skill `$pdf-to-markdown`。
- 只有当前环境明确提供 subagent/task/background worker 时，才能真正“委托转换”。否则由 main agent 按同一 gate 执行，或在无法完成时报告 blocker；不要声称有后台。
- `$pdf-to-markdown` 的 `completion.json` 证明某个 Markdown 是当前 PDF 转换流程的认证输出，不证明每道题都已逐题人工/视觉复核。
- S1 只有在题面确实对照过原 PDF 或可信来源后，才能把题目 `ocr_status` 写为 `已对照 PDF 复核`；只经过 MinerU/LLM 清理但未逐题核对时，写 `已做结构修复` 或 `待复核`。

## PPT/PPTX 课件（S8）

先用 headless LibreOffice 和独立 profile 把课件转 PDF，所有转换产物放在：

```text
90_缓存/课件转换/<deck-stem>/
```

不要打开或操控用户交互式 Office/WPS 窗口。需要抽取文本时继续走下方 PDF 路径，并保持页码与原课件一致，方便 `见 <课件名> 第N页` 指针有效。

## 标准转换契约

转换工作目录建议：

```text
90_缓存/pdf-to-markdown/<source-stem>/
```

最终 Markdown 建议：

```text
90_缓存/pdf-to-markdown/<source-stem>/final.md
```

执行 `$pdf-to-markdown` 时传入：源 PDF 绝对路径、目标 final Markdown、work dir。该 companion skill 必须完成：

1. PDF preflight 和安全分块；
2. MinerU 精确解析、上传、轮询、下载；
3. 多 chunk 时轻量 Obsidian normalization 和合并；
4. 分段 LLM readthrough repair；
5. merge repaired segments 回 final Markdown；
6. 写出 `completion.json`；
7. 成功运行 `scripts/verify_completion.py`。

父 skill 只能消费通过 `verify_completion.py` 的 `completion.json.final_markdown`。不要消费 draft、`.mineru.md`、`source/`、`repaired/`、单个 chunk 或自然语言“已经转换好了”的声明。

建议转换任务 brief：

```text
Use $pdf-to-markdown on the exact source PDF below.
Run the MinerU-first pipeline, process every LLM readthrough segment, merge repaired segments into the requested final Markdown, write completion.json, and run verify_completion.py.
Do not use fallback skills unless retries fail and the user explicitly approves.
Return success only after verify_completion.py exits 0.

Source PDF: <absolute path>
Work directory: <absolute path>
Requested final Markdown: <absolute path>
Skill root: <absolute path to pdf-to-markdown>
```

## Gate 0：运行中协调

当转换由 subagent 执行时：

1. 父级对转换 work dir 保持只读。
2. 父级可以读取 `manifest.json`、`reports/` 和 completion 状态判断进展。
3. 父级不能写 final Markdown、segment repaired 文件、manifest 或 `completion.json`。
4. 若 subagent 不可用，不进入“后台等待”叙事；main agent 直接执行同一流程，或明确报告当前无法完成的最小 blocker。

短 timeout、缺最终输出或只生成 prompt package，不等于转换完成。只有 `completion.json` 验证通过才算完成。

## Gate 1：completion verification

在 S1/S8 消费 final Markdown 前，必须独立验证：

```text
python <pdf-to-markdown>/scripts/verify_completion.py --work-dir <work-dir>
```

验证通过后，读取 `completion.json`，确认：

- `status == complete`
- `source_pdf` 是当前源 PDF
- `source_pdf_sha256` 匹配当前源 PDF
- `final_markdown` 存在
- `final_markdown_sha256` 匹配当前 final Markdown
- `unresolved_count == 0`
- MinerU manifest 中无 failed/pending chunk
- LLM readthrough segment package 已处理完成

任何一项失败，都停止入库/消化，报告准确 blocker，不启动 fallback，不消费中间产物。

## Gate 2：父 skill 绑定 manifest

S1 PDF 入库在写题库后，还必须运行：

```text
python <fuck-the-class>/scripts/s1_intake_gate.py bind --course-root <course-root> --source <source-pdf> --completion <work-dir>/completion.json --output <qbank-md> --pdf-skill <pdf-to-markdown-root>
python <fuck-the-class>/scripts/s1_intake_gate.py verify --manifest <intake.json>
```

S8 课件消化在写知识文件后，还必须运行：

```text
python <fuck-the-class>/scripts/s8_digest_gate.py bind --course-root <course-root> --chapter <chapter> --source <source-file> --completion <work-dir>/completion.json --output <knowledge-md>
python <fuck-the-class>/scripts/s8_digest_gate.py verify --manifest <digest.json>
```

## Fallback 规则

- 不自动调用 legacy visual fallback、visual reconstruction 或 vision-crop skill。
- MinerU 重试、重分块后仍有 unresolved failed ranges 时，先报告失败页码、错误、已做重试和建议 fallback。
- 只有用户明确批准后，才进入 fallback。
- fallback 产物同样不能绕过 source/ocr 不确定性标记。

## 边界

- 原始源文件保留在 `00_原材料/`；清理后的题库只写 `10_题库/`。
- 转换产物不进入用户复习界面，除非用户要求检查。
- S1 永远不创建、patch 或重新解释 `completion.json`；只有 `$pdf-to-markdown` finalization 写它。
- 若 completion 通过但题面仍有图、公式或 OCR 不确定项，S1 继续用 `待复核` 或 `已做结构修复`，不要自动升级成 `已对照 PDF 复核`。
