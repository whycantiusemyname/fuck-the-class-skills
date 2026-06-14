# S8 Courseware Digest

Purpose: turn one chapter's courseware decks (PPT/PPTX/PDF) into a chapter mainline note in `20_知识/` — a guided first read during concept learning, a lookup dictionary during the sprint.

Inputs:

- course root
- chapter scope and its courseware file list
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
2. Quality bar: match the depth, length, and prose density of the golden sample `D:\FuckTheClass\电路分析\10_工作区\章节梳理\第06章_晶体管放大电路基础_主干重点.md` (a validated hand-built note). The fixed structure below is a floor, not a checklist to satisfy minimally — every section must be readable on its own.
3. Write one note per chapter with this fixed structure:
   - 这一章抓什么: review-priority list.
   - 阅读层次表: 2-4 reading layers (e.g. intuition / model / application).
   - 先建立整体直觉: multi-paragraph prose, no less than ~400 Chinese characters, that fully answers three questions — what problem the chapter solves, how it connects to the chapters before and after, and what physical picture the key formulas express as a whole. Never explain symbol-by-symbol or item-by-item; never compress this into a single short paragraph.
   - 本章怎么串起来: the chapter's mainline chain plus how to decompose its typical problems.
   - 分节主干 following deck order; write concepts as full sentences, and include **at least one `> **直觉**：` or `> **注意**：` blockquote per section** — never a bare bullet checklist. For figures that matter to problems, write "见 <课件名> 第N页" pointers instead of describing figures vaguely.
   - 解题流程: numbered step recipes per question family.
   - 易错点.
   - 复习检查: a checklist where every item points back to a section of this note.
4. Source-citation discipline: the chapter-to-deck mapping table lives ONLY in `20_知识/README.md` — do not repeat the full table inside chapter notes. Section-level sources cite the deck filename only; add page numbers only when they locate the actual pages of that section's content — **never write "第 1-<total> 页" (the whole file's page count) as a fake range**. Items in 易错点 / 解题流程 / 复习检查 point back to sections of this note by default (sections already carry their sources); per-item deck citations are reserved for pointing at a specific figure or derivation.
5. Prefer `_标签库.md` terms for question-type names. If the library does not exist yet or has no match, name freely and end the note with an `未对齐题型名` list for S1 `精标回填`.
6. Formatting discipline: inline LaTeX for single-line formulas; display blocks only for multi-line derivations or centerpiece formulas; blockquotes must fully wrap their content; keep symbols consistent across the whole note and flag conflicts between decks, following the newer deck.
7. Maintain `20_知识/README.md`: chapter-to-deck mapping, mainline/supplement hierarchy, suggested first-read order. After changing a chapter note, inspect the README and update every affected entry; if no edit is needed, report it as checked and unchanged.
8. Maintain the cross-chapter framework when `20_知识/整体知识框架.md` already exists or the user requests one: refresh every section affected by the changed chapter notes. If it does not exist and was not requested, do not create it implicitly.

Output:

- `20_知识/第XX章_主干重点.md`
- synchronized or checked-unchanged `20_知识/README.md`
- optional `20_知识/整体知识框架.md`

Boundary: do not invent exercises. Question ingestion belongs to S1, and full worked solutions belong to S9. Do not paste long verbatim runs of the deck. Formulas must agree with the decks; when decks contradict each other, point it out and follow the newer version. Do not claim S8 complete while an existing README or framework still contains content made stale by the changed chapter notes.
