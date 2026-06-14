---
name: pdf-to-markdown
description: Convert local PDF files into one high-confidence Obsidian Markdown note through MinerU, segmented LLM repair, page-by-page visual source verification, deterministic completion gates, and a hash-bound completion certificate. Use when Codex needs a MinerU-first PDF conversion whose final Markdown must not be consumed until text repair and source-PDF verification are complete.
---

# Pdf To Markdown

## Overview

Convert a local PDF into one Obsidian Markdown note with a MinerU-first workflow.

Default to:

- local file preflight
- safe chunking before upload when the PDF exceeds MinerU limits
- batch upload and polling through MinerU precise parsing
- single-chunk passthrough when MinerU returns one usable `full.md`
- merge-mode rewriting only when the PDF had to be split into multiple chunks
- one segmented LLM readthrough pass after the Markdown draft is ready
- page-by-page visual verification of repaired segments against the source PDF
- final delivery only after deterministic validation writes `completion.json`

Do not use fallback, reconstruction, or vision-crop skills in this workflow. If retries, re-splitting, or visual verification leave unresolved content, stop and report the exact blocker. A different workflow requires a separate explicit user request.

## Workflow

### 1. Prepare the workspace

Choose:

- the source PDF
- the final Markdown path
- one workspace directory for intermediate files

Recommended layout:

```text
tmp/<note-stem>/
  manifest.json
  workflow_state.json
  draft.md
  completion.json
  chunks/
  results/
  normalized/
  reports/
```

Set `MINERU_API_TOKEN` before calling MinerU scripts.

Token lookup order is:

- explicit CLI argument when a script exposes one
- current process environment
- on Windows, the user environment value stored under `HKCU\Environment`

If the token was saved as a Windows user environment variable, the scripts should auto-load it even in a fresh Codex session that did not inherit the current shell environment.

### 2. Preflight and chunk the PDF

Run `scripts/prepare_pdf_chunks.py` first.

It must:

- read the source PDF page count
- compare page count and file size against safe limits
- keep chunks at or below `180` pages and `180MB`
- recursively split oversized chunks until each chunk satisfies both limits
- stop with a hard error if a single-page chunk still exceeds the safe size limit
- write `manifest.json` with chunk metadata, retry counters, and statuses

Use `scripts/split_pdf_ranges.py` only for ad hoc manual splitting. Prefer `scripts/prepare_pdf_chunks.py` for the actual workflow because it manages recursive splitting and manifest generation.

### 3. Submit, upload, and poll MinerU

Preferred entrypoint:

```powershell
python scripts/run_pdf_to_markdown.py input.pdf output.md --work-dir tmp\my-note
python scripts/run_pdf_to_markdown.py input.pdf output.md --work-dir tmp\my-note --image-width 720
```

The positional `output.md` is the requested final path, not an immediate script output. The runner writes `draft.md` under the work directory and exits with code `3` after MinerU preparation succeeds. Code `3` means `awaiting_text_repair`, not failure and not completion. Only `scripts/finalize_pdf_to_markdown.py` may create the requested final Markdown and `completion.json`.

The runner orchestrates:

- chunk preparation
- upload URL application
- `PUT` upload per chunk
- batch result polling
- retriable resubmission
- oversize-triggered re-splitting
- result download
- normalization
- merged draft generation
- one generated segmented readthrough package for the final LLM pass
- `workflow_state.json` with source, draft, run, and hash identity

If you need to inspect or rerun one stage manually, use:

- `scripts/mineru_submit_batch.py`
- `scripts/mineru_poll_batch.py`
- `scripts/mineru_fetch_results.py`
- `scripts/normalize_obsidian_output.py`
- `scripts/merge_markdown_chunks.py`

Use these defaults unless the user clearly asks otherwise:

- `model_version=vlm`
- `enable_formula=true`
- `enable_table=true`
- `language=ch`
- `is_ocr=false`
- image width unset

If the user wants smaller images inside Obsidian, pass `--image-width <pixels>`. Treat this as a maximum width cap, not a fixed forced width. Images wider than the cap get `|WIDTH`; smaller images keep their natural size.

Do not enable OCR by default just because the PDF is difficult. Let MinerU fail first, then decide whether OCR is needed.

### 4. Respect the retry ladder

The required order is:

1. retry transient upload-link failures
2. retry transient `PUT` upload failures
3. retry transient parse failures with a new `data_id`
4. re-split chunks that still violate size or page limits
5. stop and report unresolved failed ranges
6. stop and report; do not enter another skill from this workflow

Do not skip directly from API failure to manual Codex reconstruction.

### 5. Normalize and merge

If the PDF stayed as one chunk and MinerU produced one usable `full.md`, do not normalize or rewrite the Markdown. Export `full.md` byte-for-byte to `work_dir/draft.md` and stage its sibling `images/` directory under the work directory.

Only when the PDF was split into multiple chunks should you run `scripts/normalize_obsidian_output.py` for each successful chunk result.

Normalization should stay intentionally light. It should:

- read `full.md`
- copy and rename images into `assets/<note-stem>/`
- preserve MinerU Markdown whenever it already uses Obsidian embeds
- rewrite image references only when the result is still plain Markdown or HTML image syntax
- repair only clear math-delimiter errors such as `\(...\)`, `\[...\]`, and formula-like `[ ... ]` blocks
- normalize line endings only
- avoid table restructuring, layout rewriting, and issue-detection heuristics

Then run `scripts/merge_markdown_chunks.py` to create `work_dir/draft.md`:

- sort chunks by original page range
- concatenate them into one Markdown draft with minimal interference
- keep chunk boundaries explicit instead of guessing repairs
- write lightweight merge metadata for the later LLM readthrough

Do not invent missing content during normalization or merge. Do not guess sentence joins, do not split tables, and do not rewrite layout. Limit script-side math cleanup to delimiter repair around clearly math-like content. Let the later segmented LLM pass handle broader math and formatting cleanup by actually reading the Markdown segments.

### 5.5 Run The Final Segmented LLM Readthrough

After MinerU output has been exported or merged:

- treat the generated Markdown as the base document
- generate a segmented readthrough package under `reports/llm_readthrough_segments/`
- ask the LLM to process the document segment by segment instead of relying on one giant pass
- let the LLM repair math, obvious formatting damage, and Obsidian rendering issues in each segment
- keep table structure, image paths, and section order unchanged unless a tiny local fix is required
- use [references/llm-readthrough-repair.md](./references/llm-readthrough-repair.md) as the default prompt template
- prefer the generated `reports/llm_readthrough_prompt.txt` plus the per-segment prompt files as the direct handoff artifacts
- write every segment to its matching `repaired/segment-XXX.md`, including unchanged segments
- run `scripts/validate_text_repairs.py --work-dir <work-dir>` after every repaired segment exists

The LLM pass is now the default post-processing step, not an exceptional cleanup path. The deterministic scripts should stay light and conservative; the LLM handles the final segment-by-segment formatting pass.

Do not merge repaired segments into the requested final path. Missing segments, stale run identifiers, changed source hashes, empty outputs, or changed image references must fail the text gate.

### 5.6 Run Visual Source Verification

After the text gate passes:

1. Run `scripts/prepare_visual_review.py --work-dir <work-dir>` to render every PDF page with PyMuPDF and create per-segment prompts and review records.
2. Process repaired segments in order. Inspect exactly one rendered page image at a time and locate segment content by headings, question numbers, boundary text, formulas, and tables. Start each later segment from the previous segment's boundary page; overlap is allowed.
3. Check omissions, duplicates, order, numbers, signs, subscripts, superscripts, limits, matrices, question labels, options, tables, figures, and captions.
4. Write every complete result to `reports/visual_review/verified/segment-XXX.md`. Preserve image references exactly. If no edit is needed, still create the verified file.
5. Record the segment with `scripts/record_visual_review.py`, including every inspected 1-based PDF page as one contiguous range. Segment ranges must advance in document order; boundary-page overlap is allowed. Use `passed` only when no uncertainty remains; otherwise use `blocked` and record unresolved items.

Read [references/visual-source-verification.md](./references/visual-source-verification.md) before this stage. This is source verification inside this skill, not visual reconstruction. Do not call `$pdf-to-obsidian-notes-vision-crop-with-subagent` or any other fallback skill during verification.

### 5.7 Finalize And Certify

Run:

```powershell
python scripts/finalize_pdf_to_markdown.py --work-dir tmp\my-note
python scripts/verify_completion.py --work-dir tmp\my-note
```

The finalizer must merge only `verified/` segments, require complete PDF page coverage and zero unresolved issues, recheck hashes and image references, run control-character/LaTeX/link checks, atomically write the requested final Markdown, and then write `completion.json`. A natural-language completion claim is never a substitute for a valid certificate.

### 6. Stop On Unresolved Content

If ranges still fail after retries and re-splitting, or visual verification remains uncertain:

- summarize the failed page ranges
- include the last known MinerU error
- describe what retries or re-splitting already happened
- keep the workflow blocked and do not create the requested final Markdown

Stop after reporting unresolved ranges or visual uncertainty. Do not enter, call, or silently imitate any fallback skill during this workflow. A later fallback action requires a separate explicit user request.

## Scripts

### `scripts/run_pdf_to_markdown.py`

Use as the main end-to-end runner. It produces:

- `manifest.json`
- `chunks/`
- `results/`
- `normalized/`
- `reports/`
- `draft.md` under the work directory
- `workflow_state.json` with status `awaiting_text_repair`
- `reports/llm_readthrough_prompt.txt`
- `reports/llm_readthrough_segments/`

If unresolved failures remain, it exits with code `2` and records a blocked workflow. A successful preparation exits with code `3` because the final workflow is deliberately incomplete.
When the document stays as one chunk, it exports MinerU `full.md` directly to the draft and stages `images/` under the work directory.

### `scripts/prepare_pdf_chunks.py`

Create safe chunks and initialize `manifest.json`.

### `scripts/mineru_submit_batch.py`

Apply upload URLs and upload prepared chunks in batches of at most `50` files.

### `scripts/mineru_poll_batch.py`

Poll MinerU batch results and update manifest statuses.

### `scripts/mineru_fetch_results.py`

Download `full_zip_url`, save the zip, and extract it into the chunk result directory.

### `scripts/normalize_obsidian_output.py`

Use only in merge mode after multi-chunk splitting. Rewrite image paths as needed, cap oversized images when `--image-width` is set, and repair only clear math delimiters while keeping the chunk Markdown as close to MinerU output as possible. Do not treat this script as the final formatter.

### `scripts/merge_markdown_chunks.py`

Merge successful normalized chunks into one Markdown draft with no heuristic boundary repair, and write lightweight merge metadata for the later segmented LLM readthrough.

### `scripts/prepare_llm_readthrough_segments.py`

Split the final Markdown into manageable ordered segments, create one segment file per range, and create one prompt file per segment for the later LLM repair pass.

### `scripts/merge_llm_readthrough_segments.py`

Merge repaired segment files only for inspection or debugging. Do not use this script to create a certified final note; the certified path merges only visually verified segments.

### Completion gate scripts

- `scripts/validate_text_repairs.py`: require every current-run repaired segment and preserve image references.
- `scripts/prepare_visual_review.py`: render source pages and prepare ordered visual review records.
- `scripts/record_visual_review.py`: bind one verified segment to its pages, hashes, changes, and unresolved status.
- `scripts/finalize_pdf_to_markdown.py`: enforce all gates and atomically create the final Markdown plus `completion.json`.
- `scripts/verify_completion.py`: independently recompute source/final/segment hashes and coverage before another skill consumes the result.

## References

- Read [references/mineru-api.md](./references/mineru-api.md) for the exact API constraints this skill assumes.
- Read [references/obsidian-normalization.md](./references/obsidian-normalization.md) for normalization rules.
- Read [references/llm-readthrough-repair.md](./references/llm-readthrough-repair.md) for the default segmented LLM cleanup workflow.
- Read [references/visual-source-verification.md](./references/visual-source-verification.md) for page-by-page verification and review-record rules.

## Final Check

Before delivering the result, verify:

- every submitted chunk is accounted for in `manifest.json`
- no final chunk exceeds the safe chunk limits
- every successful chunk has `full.md`
- in single-chunk mode, the staged draft remains byte-identical to MinerU `full.md` before LLM repair
- in merge mode, every rewritten image link points at an existing file
- every expected repaired and verified segment exists and belongs to the current `run_id`
- every visual review is `passed`, has zero unresolved items, and records inspected pages
- the union of inspected pages exactly covers every source PDF page
- the final Markdown is the ordered merge of current verified segments only
- control-character, LaTeX, unresolved-marker, and broken-image checks all report zero
- `completion.json` is `complete` and its source/final hashes verify
- unresolved failures are reported to the user instead of silently dropped
- no fallback, reconstruction, or vision-crop skill was called
