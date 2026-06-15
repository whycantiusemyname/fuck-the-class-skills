# S1 Paper Intake

Purpose: turn a paper, homework set, scan, photo batch, or existing text into a tagged question-bank file; also backfill knowledge-level tags onto already-ingested questions (`精标回填` mode).

Inputs:

- source file or screenshots
- course root
- mode: `入库` (default) or `精标回填`
- optional naming convention for anchors
- optional seed vocabulary: a validated tag library from an earlier project of the same course, or the `未对齐题型名` lists at the end of `20_知识/` chapter notes

Required files:

- read: source file, preferably under `00_原材料/`
- read/write: `10_题库/_标签库.md`
- read optional: `20_知识/` for chapter mapping and `未对齐题型名` lists
- write: `10_题库/<卷名>题面整理.md`
- for every PDF, including scanned PDF: verified cache `90_缓存/pdf-to-markdown/<source-stem>/` containing `completion.json`

Steps:

1. If the source is a PDF, including a scanned PDF, execute Gate 0 and Gate 1 from `pdf-ingestion.md` exactly. Continue only after the current source, certified Markdown, verified segments, page coverage, and zero unresolved items pass the independent completion verifier; never consume drafts, standalone intermediate segments, or a natural-language success claim. For standalone photos, work directly from the images and retain any visual uncertainty for user confirmation.
2. Before writing, check `90_缓存/s1-intake/*/intake.json` for the same source SHA-256. A complete existing binding means the source was already ingested; stop instead of creating duplicate anchors.
3. Cold start: when `_标签库.md` is empty or has no knowledge-level types, build the vocabulary BEFORE tagging — import the user's seed vocabulary first; without one, draft an initial knowledge-level vocabulary from `20_知识/` chapter notes (`未对齐题型名`) or the courseware table of contents. Never dump every question into form-level placeholder tags (`选择题｜待精标` and the like) just because the vocabulary is empty. Placeholder tags are allowed only for individual questions that genuinely cannot be judged, and the output must report how many and which action will resolve them.
4. Split a merged scan bundle into separate papers, then split each paper into individual questions without solving them.
5. Assign anchors using the course convention.
6. Write clean question text in Markdown with LaTeX math.
7. Add document-level `paper_type` and `academic_year`. Add per-question `chapter`, `question_type`, `question_form`, and `ocr_status`. Use `待复核` when concrete source uncertainty remains, `已对照 PDF 复核` only after source comparison, and otherwise `已做结构修复`.
8. Select `question_type` from `_标签库.md` and use its existing capability-theme mapping. When no tag fits, apply tag governance; any new tag must receive exactly one capability theme in the same operation.
9. Update `_标签库.md` counts and verify that every controlled tag has one capability theme.
10. `精标回填` mode: leave question text, anchors, and solution blocks untouched; replace placeholder/undetermined knowledge tags, fill missing `question_form` fields when requested, repair paper metadata when factual evidence exists, and complete capability-theme mappings in `_标签库.md`. Do not bulk-upgrade legacy OCR states.
11. Run `validate_course_artifacts.py --scope s1`.
12. For PDF intake, run `s1_intake_gate.py bind` with the exact source PDF, completion.json, every output paper, and the `$pdf-to-markdown` skill path. Then run `s1_intake_gate.py verify` on the written manifest. S1 is not complete until both pass.
13. Report question-form completeness, OCR-status counts, capability-theme mapping completeness, and the intake manifest path. Remind the user to regenerate S2 after any source-data change.

Output:

- `10_题库/<卷名>题面整理.md` — strictly one paper per file; merged scan bundles MUST be split into separate per-paper files
- tag-library change summary
- paper metadata, question-form completeness, and capability-theme mapping summary

Boundary: before the PDF completion gate passes, do not split questions, modify `_标签库.md`, or create/update anything under `10_题库/`. While a child conversion agent is running, the S1 parent must not write any child-owned conversion artifact or run finalization on the child's behalf. The S1 parent must never create or repair `completion.json`. The only consumable PDF text is the certificate's current `final_markdown`; `draft.md`, `.mineru.md`, `source/`, and `repaired/` are forbidden. Do not write answers or analysis in S1; route a solution request to S9 after intake.
