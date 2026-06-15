# S8 Courseware Digest

Purpose: turn one chapter's courseware decks (PPT/PPTX/PDF) into a chapter mainline note in `20_知识/` for fast exam-oriented understanding: a student should quickly find the tested idea, recognition cue, first move, formula conditions, and common trap, then be able to understand the underlying idea without unexplained jumps.

Inputs:

- course root
- chapter scope and its courseware file list
- optional root-level `课程口径.md`; when absent, use the supplied course materials as the boundary
- mainline/supplement mapping from the user (e.g. "6-5 supplements 6-4, not a mainline"). This comes from the teacher's emphasis and exam hints; never infer it yourself. If missing, ask.
- optional: existing `40_派生视图/考频矩阵.md` to mark high-frequency question types

Required files:

- read: source PPT/PPTX/PDF decks, preferably under `00_原材料/`
- read/write or create: `20_知识/README.md`
- read/write when present and affected: existing chapter notes and `20_知识/整体知识框架.md`
- read optional: `10_题库/_标签库.md` and `40_派生视图/考频矩阵.md`
- write: `20_知识/第XX章_主干重点.md` and conversion cache under `90_缓存/` when needed

Steps:

1. Convert decks through cached conversion under `90_缓存/` per `pdf-ingestion.md`; never manipulate the user's open Office windows.
2. Quality bar: use the level, notation, and vocabulary taught by the current course. Write a self-contained, plain-language guided review, not a slide inventory or a miniature textbook. Organize the note around what is tested and how the ideas are used, while supplying enough intuition, intermediate reasoning, examples, and formula conditions to remove likely comprehension gaps. `快速理解` means reducing prerequisite burden and reasoning jumps, not forcing short prose. Do not shorten material when doing so would make it harder to understand. Do not depend on a cross-course absolute-path golden sample.
3. Write one note per chapter with this fixed structure:
   - 这一章抓什么: review-priority list.
   - 阅读层次表: 2-4 reading layers (e.g. intuition / model / application).
   - 先建立整体直觉: explain what problem the chapter solves, how it connects to neighboring chapters, and the physical or geometric picture behind the main formulas. Use as many paragraphs, intermediate examples, or contrasts as needed to make the mainline understandable; there is no target minimum or maximum length.
   - 本章怎么串起来: the chapter's mainline chain plus how to decompose its typical problems.
   - 分节主干 following deck order; begin each section with a one-sentence exam-facing conclusion or recognition cue, then explain the concepts, conditions, symbols, reasoning bridges, and representative examples needed to understand and use it. Do not omit an intermediate step merely to keep the section short. Include **at least one `> **直觉**：` or `> **注意**：` blockquote per section**. Define unfamiliar source terminology on first use and prefer the ordinary name used in the course. For figures that matter to problems, write "见 <课件名> 第N页" pointers instead of describing figures vaguely.
   - 解题流程: numbered step recipes per question family.
   - 易错点.
   - 复习检查: a checklist where every item points back to a section of this note.
4. Scope gate — no syllabus expansion:
   - Resolve the boundary in this order: the current user instruction, confirmed teaching/exam scope in `课程口径.md`, user-confirmed teacher emphasis, then the supplied source materials. If the profile is absent or its range fields are `未设置`, the supplied materials are the boundary.
   - Use `学习阶段` only to choose familiar terminology, unpack assumed prerequisites, and decide how many reasoning bridges or examples are needed. Never treat the stage label as permission to add content.
   - Do not replace a course statement with a stronger formulation or introduce outside notation, proof machinery, terminology, or methods merely because they are elegant or commonly taught elsewhere.
   - Plain-language analogies may clarify an in-scope idea, but may not add a new theorem, notation system, proof method, or examinable conclusion.
   - The question bank and tag vocabulary may prioritize topics and standardize names, but cannot authorize a theory that is absent from the confirmed scope and source materials.
   - If the decks themselves contain material identified as supplementary or outside the exam mainline, omit it from required formulas and solution recipes. Include it only when needed to represent the deck faithfully, under `课件拓展（非应试主线）`, without presenting it as required knowledge.
   - When a statement, term, or formula cannot be traced to the source materials or confirmed scope, omit it and list it under `范围待确认`; never fill the gap from general model knowledge.
5. Source-citation discipline: the chapter-to-deck mapping table lives ONLY in `20_知识/README.md` — do not repeat the full table inside chapter notes. Section-level sources cite the deck filename only; add page numbers only when they locate the actual pages of that section's content — **never write "第 1-<total> 页" (the whole file's page count) as a fake range**. Every nontrivial formula, criterion, and named method must be traceable to a cited source section. Items in 易错点 / 解题流程 / 复习检查 point back to sections of this note by default; per-item deck citations are reserved for a specific figure or derivation.
6. Prefer `_标签库.md` terms for question-type names. If the library does not exist yet or has no match, name freely and end the note with an `未对齐题型名` list for S1 `精标回填`.
7. Formatting discipline: inline LaTeX for single-line formulas; display blocks only for multi-line derivations or centerpiece formulas; blockquotes must fully wrap their content; keep symbols consistent across the whole note. When decks conflict, follow the user-confirmed mainline source. If no source priority resolves the conflict, mark it `范围待确认` instead of silently choosing the newer deck.
8. Maintain `20_知识/README.md`: chapter-to-deck mapping, mainline/supplement hierarchy, suggested first-read order. After changing a chapter note, inspect the README and update every affected entry; if no edit is needed, report it as checked and unchanged.
9. Maintain the cross-chapter framework when `20_知识/整体知识框架.md` already exists or the user requests one: refresh every section affected by the changed chapter notes. If it does not exist and was not requested, do not create it implicitly.
10. Before validation, perform a scope audit and report `范围复核：课件外理论 0，未确认术语 0` or list each unresolved item. Any unresolved scope item blocks completion or stays out of the note.
11. Run `validate_course_artifacts.py --scope s8`.
12. Run `s8_digest_gate.py bind` with every source deck/PDF, every applicable PDF completion certificate, and every changed chapter note/README/framework output. On an intentional refresh, use `--replace`. Finish by running `s8_digest_gate.py verify`.

Output:

- `20_知识/第XX章_主干重点.md`
- synchronized or checked-unchanged `20_知识/README.md`
- optional `20_知识/整体知识框架.md`

Boundary: do not invent exercises or import outside-syllabus theory. Question ingestion belongs to S1, and full worked solutions belong to S9. Do not paste long verbatim runs of the deck. Do not claim S8 complete while scope or a source conflict is unresolved, while an existing README or framework still contains content made stale by the changed chapter notes, or while its digest manifest is absent or stale.
