# S4 Practice Queue

Purpose: generate "what should I do now?"

Inputs:

- question count `N`
- optional chapter or question-type scope
- optional mode: `常规`, `只出红区`, or `起手训练`

Required files:

- read: `10_题库/*.md`
- read: `10_题库/_标签库.md`
- read: `30_我的数据/做题记录.md`
- read: `30_我的数据/卡点清单.md`
- read optional: `40_派生视图/考频矩阵.md`
- write: `40_派生视图/当日队列.md`

Steps:

1. Derive mastery states from `做题记录.md`.
2. Rank by `frequency x mastery urgency x score`.
3. Put unresolved red items first.
4. Run `卡点检验`: if `卡点清单.md` contains a question type or mapped concept with no attempt records, raise its priority and actively sample questions for it. This specifically tests concepts that were hard during learning but have not yet appeared in practice data.
5. Use never-attempted real questions before repeats within the same type. Skip questions marked `ocr_status: 待复核` by default, or include them only with a prominent warning that the question surface may be corrupted and needs checking against the original PDF first.
6. Include green-zone sampling only when useful and keep it at or below 15% of the queue.
7. Exclude user-confirmed abandoned types.
8. In `起手训练`, list only clean question links and ask for type judgement plus first move, not full solutions.

Output:

- `40_派生视图/当日队列.md`

Boundary: `N` is user-provided. Do not decide the day's workload.
