# S3 Grading Intake

Purpose: process handwritten screenshots from `30_我的数据/inbox/`.

Inputs:

- inbox images
- mode: `日常` by default, `整卷` when the user asks

Required files:

- read: `30_我的数据/inbox/*`
- read: matching question files under `10_题库/`
- read/write: `30_我的数据/做题记录.md`
- write/move: `30_我的数据/archive/`
- write optional: `40_派生视图/整卷失分统计.md`

Steps:

1. Assign a stable `batch-id` and run `s3_batch_gate.py prepare` with every inbox image before grading. If the batch file already exists, read its state and resume it; do not create a second batch.
2. Read each screenshot only enough to identify the handwritten anchor and grade the attempt.
3. If an anchor is unclear, list the image and ask the user; do not guess.
4. Compare the attempt with the question; if a folded solution block exists under the question, use it as the grading reference (prefer status `已对照一致` or `与参考答案不一致（已裁决）`); otherwise solve the question directly — solutions are not a hard dependency for grading.
5. For wrong or stuck attempts, identify the first divergence point: the step and the nature of the deviation.
6. Propose one append row per attempt using the fixed judgement and wrong-cause vocabularies.
7. Ask for one confirmation batch before writing records, and explicitly ask which correct attempts were `对但慢` (self-report only; never infer it from screenshots).
8. After confirmation, append the rows and exactly one `<!-- s3-batch:<batch-id> -->` marker in the same write, then run `mark-recorded`. A retry that sees the marker skips this append step.
9. Rename each image as `YYYYMMDD_锚点_序号.png`, move it into `archive/`, and run `mark-moved` after each successful move. When all images are archived, run `finalize` and `verify`.
10. In `整卷` mode, additionally regenerate a score/loss breakdown in `40_派生视图/`.
11. Run `validate_course_artifacts.py --scope s3` before reporting completion.

Output:

- appended attempt rows
- grading report with divergence points
- optional whole-paper loss report

Boundary: do not transcribe full handwritten work. If grading confidence is low, mark it low-confidence and wait for confirmation. Never delete or clear an inbox image before its archive destination exists and the batch log records the move.
