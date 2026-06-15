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
5. Use never-attempted real questions before repeats within the same type. Hard-skip questions marked `ocr_status: 待复核`. A queue run cannot override this; route the question to S1 source verification first. Legacy missing status reads as `已做结构修复`.
6. Include green-zone sampling only when useful and keep it at or below 15% of the queue.
7. Exclude user-confirmed abandoned types.
8. In `起手训练`, list only clean question links and ask for type judgement plus first move, not full solutions.
9. In `只出红区`, an empty red set produces an explicit empty queue with the reason. Do not silently switch to `常规`, add yellow items, or invent a workload.
10. Run `validate_course_artifacts.py --scope s4`.

Output:

- `40_派生视图/当日队列.md`

Boundary: `N` is user-provided. Do not decide the day's workload.
