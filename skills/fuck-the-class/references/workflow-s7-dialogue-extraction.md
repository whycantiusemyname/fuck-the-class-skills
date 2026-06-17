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

1. Archive the dialogue before extraction.
   - If the exported dialogue is outside the vault or course tree, copy it byte-for-byte into `<course-root>/90_缓存/s7-dialogue/`.
   - If a same-name cached file exists with different bytes, append the source SHA-256 first 8 hex characters before the extension.
   - Use the cached vault-root-relative path for every `evidence_source` and `quote_source`.
2. Read the cached dialogue as evidence, not as source material to summarize.
3. Extract only four current item types:
   - `用户提问`: direct user questions worth remembering as concept blockers
   - `明确疑问`: user confusion, being stuck, asking for a different explanation, asking to connect pages, asking for examples, pointing out inconsistency, or asking for another angle
   - `被纠正的误解`: corrected misunderstandings in the form `原以为X -> 实际是Y`
   - `最终讲通解释`: the final explanation for a recorded prior question or clear doubt
4. Do not write new `追问≥2轮` items. Treat existing `追问≥2轮` records in old blocker lists as historical compatible data only.
5. Apply admission rules before writing:
   - A single clear doubt is enough; do not require two follow-up rounds.
   - Plain progress markers such as "continue", "next page", "start this section", or image-only turns do not qualify unless paired with a clear doubt.
   - A `最终讲通解释` must have a corresponding earlier `用户提问` or `明确疑问`; do not quote ordinary explanations that were not triggered by a visible blocker.
   - Compare against `20_知识/`; skip ordinary knowledge summaries and explanations that merely duplicate existing notes. Do not reject a real user blocker just because the same concept also appears in `20_知识/`.
6. For each accepted item, attach:
   - chapter label
   - `_标签库.md` question-type tag when it matches; otherwise `题型: 未映射`
   - `概念键` as a stable short concept path, especially when `题型` is `未映射`
   - `evidence_source`, `evidence_source_sha256`, and exact 1-based `evidence_lines`
7. Before each new item, write an idempotency marker:

```markdown
<!-- s7-item:<source_sha256>:<类型>:<evidence_lines> -->
```

   If the same marker already exists in `卡点清单.md`, skip that item and count it as a duplicate skip in the report.
8. For final explanations, paste the original excerpt as a quote block exactly as exported. Record `quote_source`, the source file SHA-256, exact 1-based `quote_lines`, and the quote SHA-256 using the schema format.
   - Quote the smallest continuous original excerpt that captures the explanation.
   - Preferred quote length is 5-25 lines.
   - If `quote_lines` spans more than 25 lines, add `quote_scope_reason:` immediately before `原文摘录` explaining why the long continuous excerpt is necessary.
   - Do not stitch together non-contiguous excerpts.
9. Append accepted items under the matching chapter in `30_我的数据/卡点清单.md`.
10. Run `validate_course_artifacts.py --scope s7`; any source-hash, line-range, quote-hash, verbatim-text mismatch, duplicate new marker, malformed new marker, missing new evidence field, or missing long-quote reason blocks completion.
11. Report extraction counts by item type and list items skipped because they duplicated `20_知识/`, lacked enough evidence, were progress-only turns, or already existed by marker.

Output:

- appended `卡点清单.md` entries
- extraction summary with counts for the four current item types and skip counts

Boundary: do not summarize knowledge, evaluate the user's ability, or give study advice. Do not rewrite original excerpts; preserve them verbatim.
