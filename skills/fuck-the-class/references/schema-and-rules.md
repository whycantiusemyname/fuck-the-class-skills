# Schema And Rules

## Course Layout

Use one folder per course:

```text
<学科>/
├── 课程口径.md       # course level, confirmed scope, emphasis, and exclusions
├── 00_原材料/        # read-only courseware, scans, homework originals
├── 10_题库/          # source of truth: questions, tags, and folded solution blocks (S9)
│   └── _标签库.md    # controlled tag vocabulary, counts, governance
├── 20_知识/          # chapter notes used as a lookup dictionary
├── 30_我的数据/
│   ├── inbox/        # new handwritten screenshots
│   ├── archive/      # processed screenshots
│   ├── 做题记录.md   # append-only attempt table
│   └── 卡点清单.md   # conceptual blockers from dialogue and mistakes
├── 40_派生视图/      # regenerated frequency views, queues, reports, cram packs
└── 90_缓存/          # OCR, conversion, and temporary intermediate files
```

S0 must create the complete skeleton, including seed files. When prerequisites are missing, S1-S9 may create only the action-specific seed files permitted by their workflow, and must report those creations. Normal workflow outputs are created as specified below; unrelated parts of the course tree must not be initialized silently.

Never move existing user files unless the workflow explicitly requires it and the move is reversible or confirmed.

## Seed Files

S0 creates these files if missing:

```text
课程口径.md
10_题库/_标签库.md
30_我的数据/做题记录.md
30_我的数据/卡点清单.md
```

Use these minimal templates.

Create `课程口径.md` through `scripts/course_profile.py init`; do not hand-roll a variant. Its required structure is:

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

`学习阶段` is free text and adjusts explanation style and assumed prerequisites only. It never expands scope. Scope precedence is: current user instruction, confirmed range in this file, user-confirmed teacher emphasis, then supplied course materials. When the file is missing in a legacy course, continue without creating it implicitly and use supplied materials as the boundary. The question bank and tag library may show emphasis and naming, but cannot independently authorize theory absent from the confirmed scope or materials.

`10_题库/_标签库.md`:

```markdown
# 标准标签库

> 本文件是本课程题型标签的唯一词表。打标先从这里选；新增、合并、计数都在这里维护。

## 字段规则

- `chapter`:
- `question_type`: 使用 `主类｜子类`，必要时三级。
- `capability_theme`: 每个知识点标签必须且只能属于一个稳定能力主题。

## 标准题型词表

## 稀疏标签合并记录

## 维护规则

- 先从现有词表中选，不新造词。
- 新标签必须能覆盖至少 2 题，或语义明显独立且有长期检索价值。
- 新增标签前反查旧卷，确认不是已有标签的改写。
- S1 修改题库后同步更新题数计数。
```

`30_我的数据/做题记录.md`:

```markdown
# 做题记录

| 日期 | 锚点 | 判定 | 错因 | 一句话 | 截图 |
|---|---|---|---|---|---|
```

`30_我的数据/卡点清单.md`:

```markdown
# 卡点清单

> 本文件连接概念学习和刷题证据。S7 追加学习对话卡点；S5 可追加做题暴露出的概念卡点。
```

Derived files in `40_派生视图/` are not seed files. Create them only when S2/S4/S5/S6 runs.

## Required Files By Action

Use this as the preflight checklist:

| Action | Required input files | Required source files | Output files |
|---|---|---|---|
| S0 setup/check | course root, optional learning stage and range statements | none | full directory tree, `课程口径.md`, `_标签库.md`, `做题记录.md`, `卡点清单.md` |
| S1 paper intake | paper/PDF/photo/text source, preferably in `00_原材料/`; for PDF including scanned PDF, verified `90_缓存/pdf-to-markdown/<stem>/completion.json` | `10_题库/_标签库.md`; `20_知识/` optional for chapter mapping | `10_题库/<卷名>题面整理.md`, updated `_标签库.md`, required PDF conversion cache when applicable |
| S2 frequency analysis | target exam or scope when known | all `10_题库/*.md`, `_标签库.md`; optional `做题记录.md`, `卡点清单.md`, and `20_知识/` | `40_派生视图/考频矩阵.md`, `40_派生视图/主题题表.md` |
| S3 grading intake | `30_我的数据/inbox/*` screenshots | matching `10_题库/*.md`, `做题记录.md`, optional folded solution blocks under matching questions | appended `做题记录.md`, moved files in `archive/`, optional whole-paper derived report |
| S4 practice queue | question count `N` | `10_题库/*.md`, `_标签库.md`, `做题记录.md`, `卡点清单.md`, optional `考频矩阵.md` | `40_派生视图/当日队列.md` |
| S5 mistake review | optional date range | `做题记录.md`, `卡点清单.md`, `10_题库/*.md`, `20_知识/`, optional `课程口径.md` | `40_派生视图/复盘报告.md`, optional appended `卡点清单.md` |
| S6 cram pack | exam scope/time if provided | `做题记录.md`, `卡点清单.md`, `10_题库/*.md`, `_标签库.md`, optional `课程口径.md`, `考频矩阵.md`, and `复盘报告.md` | `40_派生视图/冲刺包.md`, optional mock paper |
| S7 dialogue extraction | exported chat `.md`/`.txt` | `卡点清单.md`, `20_知识/`, `_标签库.md` | appended `卡点清单.md`, extraction summary |
| S8 courseware digest | chapter scope, courseware mapping, and mainline/supplement decisions | source decks, optional `课程口径.md`, current `20_知识/README.md` when present, existing affected chapter/framework notes, optional `_标签库.md` and `考频矩阵.md` | `20_知识/第XX章_主干重点.md`, synchronized `README.md`, synchronized existing `整体知识框架.md` when affected |
| S9 verified solutions | selected question anchors, optional reference answers | matching `10_题库/*.md` question surfaces, optional `课程口径.md` | folded solution blocks written directly under selected questions, unresolved-item list |

## Question Anchors

Use globally unique anchors:

```text
<年份>-<卷类>-<题号>
```

Examples: `24-25期中-算7`, `23-24期末-选3`, `章节卷-填2`.

Each question-bank entry should use the anchor as the heading or include it in the heading so practice queues can link back to a clean question surface.

## Link Convention

The reader is Obsidian; the vault root is the study root directory that contains all course folders (e.g. `D:\FuckTheClass`). Rules:

- Cross-file links use vault-root-relative wikilinks: `[[<course>/10_题库/<file>#<anchor>|label]]`.
- In-document section links use `[[#heading]]`.
- Never use `[[../...]]` relative-path wikilinks — Obsidian does not reliably resolve them.
- Hidden tags keep Obsidian comment syntax `%% %%`.

## Hidden Question Tags

Store machine-readable tags in Obsidian comment blocks near each question:

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

Required fields are `chapter` and `question_type`. New S1 intake must also write `question_form` and `ocr_status`; older entries may omit them and use the compatibility rules below. Keep optional fields short and factual.

`question_form` uses this closed vocabulary:

- `选择题`
- `填空题`
- `计算题`
- `证明题`
- `应用题`
- `简答题`
- `综合题`
- `未判定`

For older entries, resolve question form in this fixed order: explicit `question_form`, then anchor inference (`-选` / `-填` / `-算` / `-证` / `-应`), then `未判定`. Never infer form from score.

`ocr_status` uses this closed vocabulary:

- `待复核`: a concrete OCR, figure, formula, or source uncertainty remains. S4 and S9 must not consume the question by default.
- `已做结构修复`: no known unresolved defect is recorded, but the question has not been checked question-by-question against a certified source.
- `已对照 PDF 复核`: the question surface has been checked against certified PDF-derived Markdown or the source PDF.

For legacy entries without `ocr_status`, read them as `已做结构修复` for compatibility. Never write that default back as an upgrade, and never infer `已对照 PDF 复核` from a clean-looking surface.

## Paper Metadata

New S1 intake must place factual paper metadata in the document-level hidden block:

```markdown
%%
chapter: 综合
question_type: 真题整卷｜期末
source: 2023-2024期末A
paper_type: 期末
academic_year: 2023-2024
%%
```

`paper_type` should use the exam population name such as `期中`, `期末`, or `其他`. `academic_year` must use `YYYY-YYYY` with consecutive years. Legacy files may infer both from `source`; an unknown year may participate in total frequency but never in time-trend calculations.

The document-level block must be immediately adjacent to the first H1-H6 heading and must contain at least one of `paper_type`, `academic_year`, or the paper-level `source`. Do not scan past the first heading or borrow a later question block as paper metadata.

When presenting percentages or percentage-point changes, multiply the stored decimal by 100 and round to an integer with decimal `ROUND_HALF_UP`. This applies equally to positive and negative half values, so `-37.5` displays as `-38`.

## Solution Blocks

Verified solutions (S9) live directly under each question as an Obsidian folded callout — collapsed by default so the question surface stays clean while practicing:

```markdown
> [!note]- 解答｜状态：已对照一致
> （complete steps, each with its justification）
> 起手：one-line correct first move (consumed by the S6 保底清单).
```

Status values are closed: `已对照一致` / `与参考答案不一致（已裁决）` / `独立解答未对照` / `存疑`. Only S9 writes or updates these blocks; they never alter question text, anchors, or tags.

## Attempt Records

`30_我的数据/做题记录.md` is append-only:

```markdown
| 日期 | 锚点 | 判定 | 错因 | 一句话 | 截图 |
| 2026-06-11 | 24-25期中-算7 | 错 | 计算错 | 拉格朗日方程组漏解一组 | [[微积分/30_我的数据/archive/20260611_24-25期中-算7_01.png]] |
```

Judgement vocabulary is closed:

- `对`
- `对但慢`
- `卡`
- `错`
- `空`

Wrong-cause vocabulary is closed:

- `概念错`
- `起手错`
- `计算错`
- `审题错`
- `没思路`

Leave wrong cause blank for `对` and `对但慢`. `对但慢` requires user self-report; do not infer it from screenshots.

Every S3 confirmation batch appends exactly one hidden marker together with its rows:

```markdown
<!-- s3-batch:<batch-id> -->
```

The matching `90_缓存/s3-grading/<batch-id>.json` is the recovery source. A retry that finds the marker must resume image archival and must not append the rows again.

## Blocker List

`30_我的数据/卡点清单.md` bridges concept learning and practice evidence. S7 appends concept-stage blockers from learning-dialogue exports; S5 may add concept blockers observed from mistakes.

Prefer this shape:

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

New S7 items must carry an idempotency marker immediately before the item:

```markdown
<!-- s7-item:<source_sha256>:<类型>:<evidence_lines> -->
```

For new S7 items, every item type must carry these evidence fields:

```markdown
  evidence_source: <vault-root-relative cached dialogue path>
  evidence_source_sha256: <source file SHA-256>
  evidence_lines: <1-based start>-<1-based end>
```

Every `最终讲通解释` quote must also carry these quote fields immediately before `原文摘录`:

```markdown
  quote_source: <vault-root-relative exported dialogue path>
  quote_source_sha256: <source file SHA-256>
  quote_lines: <1-based start>-<1-based end>
  quote_sha256: <UTF-8 SHA-256 of the exact quoted lines joined by LF>
```

If `quote_lines` spans more than 25 lines, add this field immediately before `原文摘录`:

```markdown
  quote_scope_reason: <why the continuous long excerpt is necessary>
```

Current S7 item types are closed:

- `用户提问`
- `明确疑问`
- `被纠正的误解`
- `最终讲通解释`

Legacy S7 item type compatibility:

- Existing `追问≥2轮` records remain valid historical data.
- Do not write new `追问≥2轮` records; use `明确疑问` for new extraction when the user shows a real doubt.

S7 rules:

- Extract only the four current item types for new records.
- A single clear doubt is enough for `明确疑问`; do not require two follow-up rounds.
- Progress-only turns such as "continue", "next page", or "start this section" are not blockers unless paired with a real doubt.
- A `最终讲通解释` must have a corresponding earlier `用户提问` or `明确疑问`; ordinary explanations without a visible blocker are not quoted as final explanations.
- Skip material that merely repeats `20_知识/`.
- Add `question_type` only when it matches `_标签库.md`; otherwise leave it blank or mark `未映射`.
- Add `概念键` as a stable short concept path for S7/S4/S5 weak association, especially when `题型` is `未映射`. `概念键` is not a question-type tag and must not modify `_标签库.md`.
- When the dialogue export is outside the vault or course tree, copy it byte-for-byte into `<course-root>/90_缓存/s7-dialogue/` and use the cached vault-root-relative path for `evidence_source` and `quote_source`.
- Preserve `最终讲通解释` excerpts verbatim as block quotes. Do not rewrite, polish, compress, translate, or silently fix wording.
- Keep final-explanation excerpts to the smallest continuous original passage that captures the explanation. Prefer 5-25 lines; use `quote_scope_reason` for longer excerpts.
- Keep S7 output as evidence extraction, not a knowledge summary or study plan.

S4 and S5 consume this file:

- S4 raises priority for blocker-linked question types that have no attempt records.
- S5 marks a question type as `确认顽固弱点` when it appears both as a concept blocker and as a `概念错` mistake.

## Tag Governance

Question-type tags use `主类｜子类`, with a third level only when it has durable retrieval value.

Rules:

- Select from `_标签库.md` first.
- Store the stable capability theme beside every controlled knowledge tag in `_标签库.md`; each tag maps to exactly one theme.
- Do not create a new tag for a one-off phrasing difference.
- Add a tag only when it can cover at least two questions, or when it is semantically independent and useful for future retrieval.
- Before adding, check whether old papers already contain an equivalent tag.
- Prefer merging sparse variants upward when the distinction will not change practice decisions.
- Update `_标签库.md` counts whenever S1 changes `10_题库/`.
- When adding or merging a tag, update its capability-theme mapping in the same S1 operation. S2 consumes this mapping and must not invent or repair it.

## Mastery State

Derive mastery by question type from `做题记录.md`; do not store it as a separate source file.

- `未接触`: no record for this question type.
- `红`: latest attempt is `错` or `空`.
- `黄`: latest attempt is `卡` or `对但慢`, or the first `对` after a red state.
- `绿`: two consecutive `对` attempts on different days.

Any `错` or `空` immediately returns the type to `红`.

## Derived Views

Every file in `40_派生视图/` must begin with:

```markdown
> 派生文件，可重新生成，勿手改。
```

Regenerate derived files from source data. Do not manually patch a single count, queue item, or row unless the user explicitly asks to edit the rendered view and understands it is derived.

## Output Self-Check

Every skill that writes course artifacts must run this check BEFORE reporting completion, and include a one-line result in the report (e.g. `自检：控制字符 0，LaTeX 异常 0，断链 0`). Fix findings before delivering.

Run the shared gate instead of improvising one-off scans:

```text
python <skill>/scripts/validate_course_artifacts.py --course-root <course-root> --scope <s1|s2|s3|s4|s5|s6|s7|s8|s9|all>
```

Exit code `0` passes, `2` means artifact findings must be fixed, and `3` means the requested course or scope is invalid. For S2, the same command also verifies the analysis input fingerprint and byte-for-byte JSON-to-Markdown rendering.

1. Control characters: file bodies must not contain invisible control characters (`\x00-\x08`, `\x0B`, `\x0C`, `\x0E-\x1F`). Backslashes in LaTeX get eaten by shell string escaping (real cases: `\frac` → form-feed + `rac`, `\qquad` → `qquad`, `\,` → `,`); the damage is invisible to eyeballing, so scan with a regex.
2. LaTeX corruption patterns: backslash-less remnants of `qquad/quad/frac/left/right`; every `\left` paired with a `\right`; balanced `$`/`$$` delimiters. Suspected naked math outside delimiters is a warning for human review, not a hard failure, because ordinary Chinese prose can contain formula-like text.
3. Links: every in-document link target (file and heading anchor) must actually exist.
4. Root-cause prevention: write backslash-heavy content through file-writing tools, never through shell string interpolation.
