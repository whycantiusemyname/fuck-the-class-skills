# S9 Verified Solutions

Purpose: add verified folded solution blocks directly under selected questions in `10_题库/`, for S3 grading and pre-exam reference. Cover on demand (high-frequency types, today's queue, cram-pack questions) — never the whole bank in one pass.

Inputs:

- course root
- anchor scope (e.g. "all questions in today's queue", "1-2 questions per top-20 high-frequency type")
- optional reference answers: many paper scans carry a QR code linking to official/reference answers — the user scans and provides them as images or text; if QR images already exist in OCR artifacts, decoding them is allowed

Required files:

- read/write: question-bank files containing the selected anchors under `10_题库/`
- read optional: user-provided reference-answer images or text
- write: folded solution blocks in those same question-bank files; no separate answer directory

Steps:

1. Refuse selected questions marked `ocr_status: 待复核`; route them to S1 source verification before solving.
2. With a reference answer: solve independently first → compare → if they agree, finalize. If they disagree, solve a second time and adjudicate whether the error is yours or the reference's (reference answers are NOT guaranteed correct); state the evidence for the verdict. Still unsure → mark `存疑` and leave it for the user.
3. Without a reference answer: solve once, then self-check key steps (special-case substitution, reverse verification, magnitude/dimension checks); explicitly mark any step that cannot be self-verified.
4. Write each solution as a folded callout block directly under its question (format in `schema-and-rules.md` → Solution Blocks), collapsed by default so the question surface stays clean.
5. Title line carries the status: `已对照一致` / `与参考答案不一致（已裁决）` / `独立解答未对照` / `存疑`.
6. Every block ends with a one-line correct first move (consumed directly by the S6 保底清单).
7. Run `validate_course_artifacts.py --scope s9`.

Output:

- folded solution blocks added under the selected questions
- a list of `存疑` items needing user adjudication

Boundary: only add or update solution blocks — never modify question text, anchors, or tags. Solutions are not a hard dependency for S3: simple questions are graded reliably by solving directly; spend S9 effort on hard and high-score questions.
