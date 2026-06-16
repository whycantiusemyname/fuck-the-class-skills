---
name: fuck-the-class
description: "Fast, understandable, source-bound exam-cram workflow for turning course folders, PDFs, scans, homework, screenshots, attempts, learning dialogues, question banks, tags, mistakes, and reference answers into controlled question banks, verified solutions, deterministic frequency and trend views, practice queues, grading records, blocker lists, reviews, and cram packs without expanding beyond the confirmed course scope. Use when the user invokes Fuck The Class or asks to initialize or organize a course, ingest papers, classify questions, analyze frequency or recent trend shifts, detect newly hot topics or question-form changes, grade work, digest courseware, extract blockers, verify solutions, generate practice, review mistakes, or make a cram pack. Also use for 应试冲刺, 快速理解课程, 新学科初始化, 课程文件夹整理, 试卷入库, 题型分类, 考频分析, 趋势预警, 近期热点, 题型变化, 考法迁移, 批改截图, 学习对话提取, 卡点清单, 课件梳理, 章节梳理, 配解答, 核验解答, 出题队列, 错因复盘, and 冲刺包."
---

# Fuck The Class

## Overview

Use this skill to run one exam-prep action at a time for a course. Optimize for fast exam gains and fast understanding: expose what to recognize, remember, do first, and check, then explain the idea with enough intuition and intermediate reasoning to make it genuinely understandable. Fast understanding means low cognitive friction, not minimum word count. The user controls the rhythm; the skill performs the requested action, writes the requested artifact, reports what changed, and stops.

This skill serves university learners across undergraduate and graduate courses. It is course-agnostic and assumes a controlled local folder: raw course materials, question-bank source files, user attempt records, and derived review views are separated so future work has a single source of truth.

## Start Every Task

1. Identify the course root. If the user did not give one, infer it from the current workspace only when it is unambiguous; otherwise ask for the course folder and the desired action.
2. Identify the action:
   - S0 course setup: initialize or audit a new subject folder with every required directory and seed file.
   - S1 paper intake: ingest a paper, homework set, PDF, scan, photo, or existing text into `10_题库/`.
   - S2 frequency analysis: regenerate deterministic importance, time-trend, question-form-shift, and theme question-table views from the question bank.
   - S3 grading intake: process handwritten screenshots from `30_我的数据/inbox/`.
   - S4 practice queue: generate a queue for now.
   - S5 mistake review: summarize wrong causes and prescriptions.
   - S6 cram pack: produce the final pre-exam checklist, starter drill, and reminder card.
   - S7 learning-dialogue extraction: extract concept-stage blockers from exported AI chat records into `卡点清单.md`.
   - S8 courseware digest: turn chapter courseware decks into mainline notes in `20_知识/`.
   - S9 verified solutions: add checked solutions as folded callout blocks under selected questions in `10_题库/`.
   - setup/check: alias for S0.
3. Read [references/schema-and-rules.md](./references/schema-and-rules.md) before writing or validating any course artifact.
4. Read `<course-root>/课程口径.md` when present. Apply scope and explanation guidance in this order: the current user instruction, confirmed teaching/exam scope, user-confirmed teacher emphasis, then the supplied course materials. `学习阶段` adjusts explanation and assumed prerequisites only; it never expands the curricular boundary. If the file is absent, continue in legacy-compatible mode and use the supplied materials as the boundary.
5. Read only the workflow for the selected action; for a user-requested combined operation, read each selected workflow:
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
6. Read [references/pdf-ingestion.md](./references/pdf-ingestion.md) when a PDF, PPT/PPTX deck, scanned paper, or converted Markdown from a PDF is involved.

## Non-Negotiables

- Keep the user in control of pacing. Do not create schedules, daily plans, or "tomorrow" recommendations unless the user asks for that specific artifact.
- Preserve single sources of truth: questions, tags, and folded solution blocks live in `10_题库/`; attempt records live in `30_我的数据/做题记录.md`; derived views live in `40_派生视图/`.
- Treat `00_原材料/` as read-only.
- Keep learning and review artifacts exam-oriented and easy to understand. Organize them around tested concepts, recognition cues, first moves, formula conditions, and common errors, using the course's familiar language. For knowledge notes, prefer a teacher-friendly guided explanation that a student can follow: introduce methods through what to notice, why the first move works, what each formula symbol is doing, when the method is valid, and what mistake it prevents. Keep final recipes and checklists scannable, but do not turn the main explanation into only a compact reference outline. Never compress away prerequisites, reasoning bridges, examples, or formula conditions needed for understanding. Concision is secondary to clarity; explanation may be as long as necessary while remaining structured and easy to navigate.
- Stay inside the current course scope. Do not introduce theories, notation, proof machinery, or terminology absent from the source materials and confirmed teacher/exam scope. Plain-language analogies may clarify existing material, but must not add curricular content. When scope is uncertain, omit the material and report it for confirmation. Question-bank frequency may prioritize an in-scope topic but cannot authorize new theory by itself.
- Never transcribe handwritten work into long-form text. Handwritten screenshots are evidence files; text records contain only the AI-generated judgement, wrong-cause label, one-sentence diagnosis, and screenshot link.
- Use controlled vocabularies. Do not invent judgement labels, wrong-cause labels, or question-type tags during execution; follow the tag governance rules when a new tag is truly needed.
- Mark every derived view with `> 派生文件，可重新生成，勿手改。` at the top and regenerate the whole file instead of hand-editing fragments.
- Before any S1-S9 workflow, check the required files for that action. If the course has not been initialized, run S0 first or create only the missing action-specific seed files allowed by `schema-and-rules.md`, then report exactly what was created.
- Respect write boundaries: S1 owns question text, anchors, and tags under `10_题库/` and updates `_标签库.md`; S9 may only add or update folded solution blocks under questions; S3 may append `做题记录.md` and move processed inbox images to `archive/`; S5 and S7 may append concept blockers to `卡点清单.md`; S8 may write `20_知识/`; S2/S4/S5/S6 write derived outputs and otherwise read source data.
- For S2, run `scripts/analyze_frequency_trends.py`, then `scripts/render_frequency_views.py`; verify both the input fingerprint and byte-for-byte rendered views. Do not reimplement parsing, classifications, rendering, time windows, or trend thresholds ad hoc. S2 must remain read-only for `10_题库/` and `_标签库.md`; route source-data repairs to S1.
- For S7, preserve final explanation excerpts verbatim. Do not polish, paraphrase, summarize, or "make it clearer" when the workflow asks for an original quote.
- Do not manipulate the user's open Office or PowerPoint windows. For slides or documents, work from copies, cached conversions, or headless tools only when needed.
- If evidence is uncertain, say so and keep the uncertain item out of irreversible records until the user confirms.
- Before reporting completion of any file-writing action, run `scripts/validate_course_artifacts.py` with the selected workflow scope and include its one-line result. A prose claim or improvised scan does not replace the gate.
- Treat workflow manifests as completion evidence: S1 PDF intake requires a verified `s1-intake` manifest, S3 requires a complete grading batch, and S8 requires a current digest manifest. Do not report those workflows complete from files alone.

## PDF Dependency

For S1 and PDF-based S8 work, treat [references/pdf-ingestion.md](./references/pdf-ingestion.md) as the authoritative conversion and child-agent coordination contract; do not restate, weaken, or improvise its gates. While a conversion child is running, keep the parent read-only for that cache and follow Gate 0 for waiting or handoff. Consume converted Markdown only after the child reaches a final status and Gate 1 independently verifies the completion certificate. If no child is available, the parent may execute the same conversion workflow without weakening any gate. Never consume drafts or silently enter a fallback skill.

## Output Style

Keep outputs operational:

- changed files
- decisions made from controlled vocabularies
- items needing user confirmation
- unresolved uncertainty

Avoid dashboards, decorative analytics, and broad study advice that does not change what the user should do, review, abandon, or confirm.

## Typical Combinations

- New subject: S0, then put raw files in `00_原材料/`.
- Concept learning: S8 to digest the chapter decks first, then one chapter, one AI-chat topic, export after finishing the chapter, then run S7.
- Paper setup: S1 for past papers, S2 for frequency analysis, then S3 in `整卷` mode after a timed paper.
- Daily practice: S4 for a queue, handwritten work plus screenshots, then S3.
- Diagnosis: S5.
- Final stage: S6.
