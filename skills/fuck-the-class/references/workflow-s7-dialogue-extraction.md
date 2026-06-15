# S7 Learning-Dialogue Extraction

Purpose: preserve concept-stage evidence from exported AI learning conversations by appending structured blockers to `卡点清单.md`.

Inputs:

- exported dialogue file, usually Markdown or text
- course root
- chapter number or topic, ideally from a one-chapter-one-topic chat title

Required files:

- read: exported dialogue `.md` or `.txt`
- read/write: `30_我的数据/卡点清单.md`
- read: `20_知识/`
- read: `10_题库/_标签库.md`

Steps:

1. Read the dialogue as evidence, not as source material to summarize.
2. Extract only four item types:
   - user questions
   - corrected misunderstandings in the form `原以为X -> 实际是Y`
   - concepts with at least two rounds of follow-up
   - the final explanation that made the concept click
3. For each item, attach a chapter label and, when possible, a `_标签库.md` question-type tag.
4. Compare against `20_知识/`; skip ordinary knowledge summaries and explanations that duplicate existing notes.
5. Append accepted items under the matching chapter in `30_我的数据/卡点清单.md`.
6. For final explanations, paste the original excerpt as a quote block exactly as exported. Record `quote_source`, the source file SHA-256, exact 1-based `quote_lines`, and the quote SHA-256 using the schema format.
7. Run `validate_course_artifacts.py --scope s7`; any source-hash, line-range, quote-hash, or verbatim-text mismatch blocks the append.
8. Report extraction counts by item type and list any items skipped because they duplicated `20_知识/` or lacked enough evidence.

Output:

- appended `卡点清单.md` entries
- extraction summary with counts for the four item types

Boundary: do not summarize knowledge, evaluate the user's ability, or give study advice. Do not rewrite original excerpts; preserve them verbatim.
