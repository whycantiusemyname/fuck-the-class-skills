# S2 Frequency And Trend Analysis

Purpose: answer "what matters, what is changing, how is it being tested now, and which real questions represent it?"

Inputs:

- course root
- target exam when known, such as `期中` or `期末`
- optional chapter scope
- optional `recent_year_span`; default `5`

Required files:

- read: all `10_题库/*题面整理.md`
- read: `10_题库/_标签库.md`
- read optional: `30_我的数据/做题记录.md`, `30_我的数据/卡点清单.md`, `20_知识/`, and existing folded solution blocks
- write cache: `90_缓存/s2-frequency-analysis.json`
- write views: `40_派生视图/考频矩阵.md`, `40_派生视图/主题题表.md`

## Deterministic Gate

1. Verify that `_标签库.md` uses `章节｜能力主题｜标准知识点标签｜题数` and that every knowledge tag maps to exactly one theme.
2. Run:

   ```text
   python <skill>/scripts/analyze_frequency_trends.py --course-root <course-root> --recent-year-span 5 --output <course-root>/90_缓存/s2-frequency-analysis.json
   ```

3. Stop if the command returns nonzero or JSON `status` is not `complete`. Report the exact parser, anchor, tag-count, or theme-mapping errors; do not create new derived views.
4. Before consuming an existing JSON, run the same script with `--verify <json-path>`. Reject stale input fingerprints.
5. Treat the script as authoritative for metadata parsing, legacy question-form inference, academic-year buckets, A/B paper merging, score handling, trend labels, form shifts, and method migration. Do not recalculate these with ad hoc shell or model logic.
6. Run the deterministic renderer:

   ```text
   python <skill>/scripts/render_frequency_views.py --course-root <course-root> --analysis <course-root>/90_缓存/s2-frequency-analysis.json
   ```

7. Run the renderer again with `--verify`, then run `validate_course_artifacts.py --scope s2`. Either nonzero exit blocks completion. Do not write, rewrite, or polish either Markdown view outside the renderer.

## Interpretation Rules

1. Keep exam populations separate. Never mix `期中`, `期末`, and `其他` denominators in one importance or trend claim.
2. Present three distinct layers:
   - importance: paper coverage, question load, and known-score burden;
   - time trend: `首次成势`, `沉寂后回归`, `新近升温`, `明显降温`, `稳定核心`, `周期波动`, `平稳观察`, or `样本不足`;
   - test-method change: `大题化`, `小题化`, and theme-level `考法迁移`.
3. Quote the JSON evidence with every trend claim: historical numerator/denominator, recent numerator/denominator, percentage-point change, form or median-score change, and linked representatives. A label without its raw evidence is invalid.
4. Keep objective exam evidence separate from personal urgency. Before enough attempt records exist, use neutral roles such as `高频基础`, `高频主力`, `高分杠杆`, `低频风险`, and `低频观察`.
5. Unknown-year papers contribute to total frequency only. `score <= 0` is unknown, not zero. `question_form: 未判定` stays visible in quality reporting and never counts as a small or long form.

## `考频矩阵.md`

The renderer regenerates the whole file in this order:

1. `一眼看重点`
2. `趋势预警`
3. `重点判断`
4. `期中与期末重要性`
5. `高频排序`
6. `低频与降温信号`
7. `完整趋势与分卷证据附录`

Requirements:

- Start with the exact derived marker from `schema-and-rules.md`.
- Put native Obsidian Mermaid charts first: historical vs recent coverage, coverage change in percentage points, and known-score burden. Chart axes use stable `T1...Tn` identifiers; the folded evidence table maps every identifier to the full theme name.
- Follow each chart with the same values in a collapsed `[!info]-` table.
- Keep every Markdown table in both S2 outputs inside a collapsed `[!info]-` callout. Keep headings, charts, warnings, and judgements visible.
- Split `趋势预警` by exam population. Prioritize `首次成势`, `沉寂后回归`, `新近升温`, `大题化`, `考法迁移`, and `明显降温`; show at most eight visible items per category and fold the remainder into the complete trend table.
- Sort alerts by script trend priority, absolute coverage change, recent coverage, then recent known-score burden.
- Put full tag rankings, year series, question-form evidence, and paper matrices in folded appendices.
- Distinguish `近年仍出现`, `近年消失`, and `证据不足`; never turn low frequency alone into an abandon decision.

## `主题题表.md`

The renderer gives every capability theme one stable, unique heading using the exact controlled theme name. For each exam population, show:

- objective exam role;
- primary and secondary trends;
- historical coverage to recent coverage;
- historical form structure to recent form structure;
- historical dominant tag to recent dominant tag;
- one historical representative and up to two recent representatives from the JSON.

Use vault-root-relative links for every theme and question. Add a one-line starter only when it comes from a non-`存疑` S9 solution block. S2 must not solve questions or paraphrase a knowledge note to fill a missing starter.

Output:

- `90_缓存/s2-frequency-analysis.json` — deterministic, hash-bound evidence
- `40_派生视图/考频矩阵.md` — importance, trend warnings, judgements, and folded evidence
- `40_派生视图/主题题表.md` — theme navigation with historical and recent representatives

Boundary: S2 reads source data and writes only its cache and derived views. The analysis script owns evidence and classifications; the renderer owns both Markdown files. The executing Agent may not add free-form rows or judgements after rendering. S2 must not repair question metadata, tags, counts, theme mappings, question text, or solutions; route those changes to S1.
