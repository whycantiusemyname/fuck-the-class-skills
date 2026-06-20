---
name: pdf-to-markdown
description: Convert local PDF files into one Obsidian Markdown note through the MinerU precise parsing API, with automatic preflight, safe chunking for size and page limits, result download, light deterministic normalization, and a final segmented LLM readthrough pass for math and formatting cleanup. Use when Codex needs a MinerU-first workflow for PDF-to-Markdown conversion and should only propose legacy visual fallback skills after reporting failures and receiving explicit user approval.
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
- final completion certificate writing and verification after repaired segments are merged

Do not use legacy fallback skills automatically. If retries and re-splitting still leave failed ranges, stop and report the failure ranges, reasons, and recommended fallback path. Only call a fallback skill after the user explicitly approves it.

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
6. only after explicit user approval, enter a legacy fallback skill

Do not skip directly from API failure to manual Codex reconstruction.

### 5. Normalize and merge

If the PDF stayed as one chunk and MinerU produced one usable `full.md`, do not normalize or rewrite the Markdown. Export `full.md` directly to the requested output path and copy the sibling `images/` directory beside it.

Only when the PDF was split into multiple chunks should you run `scripts/normalize_obsidian_output.py` for each successful chunk result.

Normalization should stay intentionally light. It should:

- read `full.md`
- copy and rename images into `assets/<note-stem>/`
- preserve MinerU Markdown whenever it already uses Obsidian embeds
- rewrite image references only when the result is still plain Markdown or HTML image syntax
- repair only clear math-delimiter errors such as `\(...\)`, `\[...\]`, and formula-like `[ ... ]` blocks
- normalize line endings only
- avoid table restructuring, layout rewriting, and issue-detection heuristics

Then run `scripts/merge_markdown_chunks.py` to:

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
- after all repaired segments are ready, merge them back with `scripts/merge_llm_readthrough_segments.py`

The LLM pass is now the default post-processing step, not an exceptional cleanup path. The deterministic scripts should stay light and conservative; the LLM handles the final segment-by-segment formatting pass.


### 5.6 Write And Verify completion.json

After every segment has been repaired and merged back into the requested final Markdown path, write and verify the completion certificate:

```powershell
python scripts/write_completion.py --source-pdf input.pdf --final-markdown output.md --work-dir tmp\my-note
python scripts/verify_completion.py --work-dir tmp\my-note
```

Do not report the conversion as complete before `verify_completion.py` exits `0`. The certificate is the handoff contract used by parent skills such as `$fuck-the-class`; natural-language success reports, draft Markdown, source segments, repaired segment files, and MinerU chunk outputs are not a completion certificate.

`completion.json` proves that the final Markdown is the certified output of this conversion workflow. It does not prove that every downstream course question has been manually or visually checked against the source PDF.

### 6. Escalate to fallback only with approval

If some ranges still fail after retries and re-splitting:

- summarize the failed page ranges
- include the last known MinerU error
- describe what retries or re-splitting already happened
- recommend either the whole-document fallback or local vision-crop fallback

Only after the user says yes:

- use `$pdf-to-obsidian-notes-with-subagent` for whole-document fallback
- use `$pdf-to-obsidian-notes-vision-crop-with-subagent` for local or visual-only fallback

## Scripts

### `scripts/run_pdf_to_markdown.py`

Use as the main end-to-end runner. It produces:

- `manifest.json`
- `chunks/`
- `results/`
- `normalized/`
- `reports/`
- a merged Markdown draft
- `reports/llm_readthrough_prompt.txt`
- `reports/llm_readthrough_segments/`

If unresolved failures remain, it exits non-zero and writes a fallback recommendation report instead of calling another skill by itself.
When the document stays as one chunk, it exports MinerU `full.md` directly and copies `images/` beside the output note.

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

Merge repaired segment files back into one final Markdown note after the segmented LLM pass finishes.

### `scripts/write_completion.py`

Write `completion.json` after the final Markdown has been produced and every LLM readthrough segment has a repaired output. It records source PDF hash, final Markdown hash, manifest hash, segment manifest hash, unresolved count, and the workspace path.

### `scripts/verify_completion.py`

Verify `completion.json`, hashes, successful MinerU chunks, and repaired segment presence. Parent skills should only consume `final_markdown` after this script exits `0`.

## References

- Read [references/mineru-api.md](./references/mineru-api.md) for the exact API constraints this skill assumes.
- Read [references/obsidian-normalization.md](./references/obsidian-normalization.md) for normalization rules.
- Read [references/llm-readthrough-repair.md](./references/llm-readthrough-repair.md) for the default segmented LLM cleanup workflow.

## Final Check

Before delivering the result, verify:

- every submitted chunk is accounted for in `manifest.json`
- no final chunk exceeds the safe chunk limits
- every successful chunk has `full.md`
- in single-chunk mode, the exported note sits beside a working `images/` directory
- in merge mode, every rewritten image link points at an existing file
- `reports/llm_readthrough_prompt.txt` exists for the final LLM cleanup pass
- `reports/llm_readthrough_segments/manifest.json` exists for segmented readthrough
- unresolved failures are reported to the user instead of silently dropped
- `completion.json` exists and `scripts/verify_completion.py --work-dir <work-dir>` exits `0`
- no fallback skill was called without explicit user approval
