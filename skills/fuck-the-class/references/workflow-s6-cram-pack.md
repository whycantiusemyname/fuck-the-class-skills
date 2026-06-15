# S6 Cram Pack

Purpose: produce the last-stage exam packet.

Inputs:

- course root
- exam time or scope if the user provides it
- optional request for a mock paper

Required files:

- read: `30_我的数据/做题记录.md`
- read: `30_我的数据/卡点清单.md`
- read: `10_题库/*.md`
- read: `10_题库/_标签库.md`
- read optional: `40_派生视图/考频矩阵.md`
- read optional: `40_派生视图/复盘报告.md`
- read optional: root-level `课程口径.md`
- write: `40_派生视图/冲刺包.md`
- write optional: `40_派生视图/模拟卷.md`

Steps:

1. Build `保底清单` from high-frequency types intersecting with prior mistakes. A one-sentence first move may come only from a non-`存疑` S9 solution block or an explicitly user-confirmed attempt record. Write it as `起手：<text>｜来源：S9 <anchor>` or `起手：<text>｜来源：用户确认记录 <date>`; when neither exists, keep the anchor and write `起手：待 S9`. Never solve or invent a starter during S6.
2. Build `起手训练卷` from red and yellow types, asking only for the first move.
3. Build `考场提醒卡` from the user's own top wrong causes plus S5 `确认顽固弱点`; keep it under half a page.
4. Optionally assemble a mock paper from never-attempted real questions with the real paper structure.
5. Run `validate_course_artifacts.py --scope s6`.

Output:

- `40_派生视图/冲刺包.md`
- optional clean mock paper

Boundary: reminders must come from the user's records or confirmed blocker cross-checks, not generic advice. Use the learning stage only to choose familiar wording and how much prerequisite context to retain. Do not add a concept or method merely because it is common at that stage. S6 consumes starters but never authors solution content.
