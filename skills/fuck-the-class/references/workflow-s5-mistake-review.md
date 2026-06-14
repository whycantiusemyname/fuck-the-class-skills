# S5 Mistake Review

Purpose: show what is actually blocking score gain.

Inputs:

- course root
- optional date range

Required files:

- read: `30_我的数据/做题记录.md`
- read/write: `30_我的数据/卡点清单.md`
- read: `10_题库/*.md`
- read optional: `20_知识/`
- write: `40_派生视图/复盘报告.md`

Steps:

1. Count wrong causes overall, by chapter, and by question type.
2. If there are fewer than 30 records, state that the sample is small.
3. Map the dominant cause to action:
   - `计算错`: timed redo list, no explanation-first review.
   - `起手错` or `没思路`: starter-drill list for S4.
   - `概念错`: link to matching `20_知识/` chapter notes and update `卡点清单.md`.
   - `审题错`: extract short check sentences tied to observed mistakes.
4. Run `卡点交叉`: compare `概念错` question types with `卡点清单.md`. Mark items present in both places as `确认顽固弱点` and list them separately.
5. List repeatedly failed red types as `放弃候选` or `重点攻坚候选`.

Output:

- `40_派生视图/复盘报告.md`
- optional `卡点清单.md` updates for concept blockers

Boundary: count only decision-relevant data. Do not create trend charts or decorative dashboards.
