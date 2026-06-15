# PDF Ingestion

Use this reference when S1 or S8 receives a PDF (including a scanned PDF), a PPT/PPTX deck or document that will be converted to PDF, or Markdown produced from a PDF. Standalone photo batches remain direct S1 inputs unless they are first assembled into a PDF.

## PPT/PPTX Decks (S8)

Convert decks to PDF first with headless LibreOffice using a dedicated profile, keeping all conversion artifacts under `90_缓存/课件转换/<deck-stem>/`. Never open or control the user's interactive Office/WPS windows. Then continue with the PDF path below when text extraction is needed, and keep page numbering aligned with the original deck so `见 <课件名> 第N页` pointers stay valid.

## Required Conversion Contract

For S1, prefer launching one child agent to execute `$pdf-to-markdown`. It owns:

- preflight and chunking
- MinerU precise parsing
- upload and polling
- result download
- light Obsidian normalization
- segmented LLM readthrough repair
- page-by-page visual source verification
- deterministic finalization and `completion.json`

This ownership lasts until the child reaches a final agent status or is explicitly stopped and handed off. While it is running, the parent may inspect progress but must not write child-owned conversion artifacts.

Put intermediate work under the course cache, for example:

```text
90_缓存/pdf-to-markdown/<source-stem>/
```

Pass the exact absolute source PDF, cache directory, requested final Markdown path, and `$pdf-to-markdown` skill path. Require the child to run `verify_completion.py` successfully before reporting completion. If child agents are unavailable, the parent may execute the same workflow itself, but every completion gate remains mandatory.

Suggested child-agent task:

```text
Use $pdf-to-markdown to convert the exact source PDF below.
Complete MinerU preparation, every segmented text repair, page-by-page visual source verification, finalization, and completion verification.
Write all intermediate artifacts under the exact cache directory and write the certified Markdown only to the requested final path.
After finishing each visual-review segment, immediately write both reports/visual_review/verified/segment-XXX.md and reports/visual_review/reviews/segment-XXX.json before starting the next segment. Write unchanged segments too. Do not hold several completed segments in memory for a later batch write.
Do not stop after MinerU or after generating prompts. Do not call any fallback, reconstruction, or vision-crop skill.
Return success only after verify_completion.py exits 0.

Source PDF: <absolute path>
Cache directory: <absolute path>
Requested final Markdown: <absolute path>
Skill: <absolute path to pdf-to-markdown/SKILL.md>
```

S8 may delegate the same way when useful, but it must use the same certificate gate before treating converted Markdown as courseware source.

## Rules

- Do not copy or rewrite `$pdf-to-markdown` scripts into this skill.
- Do not use legacy visual fallback, visual reconstruction, or `$pdf-to-obsidian-notes-vision-crop-with-subagent` in this conversion path.
- Do not enable OCR by default just because a scan looks difficult; let the PDF conversion workflow decide from evidence.
- Missing, invalid, incomplete, mismatched, blocked, or unresolved completion data fails the gate. Stop ingestion and report the exact blocker without initiating a fallback.
- Preserve raw source files in `00_原材料/`; write cleaned question-bank files only under `10_题库/`.
- Keep conversion artifacts out of the user's review surface unless the user asks to inspect them.
- Retain conversion evidence required by `verify_completion.py`. Presence in the cache never makes an artifact consumable: S1/S8 may consume only the current `completion.json.final_markdown` after verification. Treat unrelated tool caches as separately owned and remove them only after confirming no active workflow references them.
- Never create, patch, or reinterpret `completion.json` in S1. Only the `$pdf-to-markdown` finalizer writes it.
- Do not treat a short agent wait timeout, absent final output, or a long page-reading interval as conversion failure. Use the coordination gate below.

## Gate 0: Child Progress, Waiting, and Handoff

Apply this gate before the conversion-certificate gate whenever a child agent executes `$pdf-to-markdown`.

### Child checkpoint rule

After each manifest segment is visually reviewed, the child must immediately write:

```text
reports/visual_review/verified/segment-XXX.md
reports/visual_review/reviews/segment-XXX.json
```

The review JSON is the segment checkpoint: it records the run id, reviewed pages, hashes, changes, unresolved items, status, and review time. A segment with no corrections must still produce both files. Start the next segment only after both files exist and are non-empty. Do not batch several completed segments into one late write.

### Parent waiting rule

While the child agent status is `running`:

1. Keep the parent read-only for the conversion cache. Do not write `verified/`, `reviews/`, `workflow_state.json`, the final Markdown, or `completion.json`; do not run finalization.
2. Use waits measured in minutes for page-by-page review. A 10-second timeout is only a status probe and cannot justify takeover.
3. After a wait timeout, inspect the child status and segment checkpoint count. Use `probe_pdf_progress.py snapshot` before and after the interval and `probe_pdf_progress.py compare`; a timestamp change alone is not substantive progress. If status, completed segments, or reviewed-page coverage advanced, continue waiting.
4. If neither advanced, send one concise status request and wait through a second multi-minute interval.
5. Only after two consecutive no-progress checks and no substantive child response may the parent request interruption or closure. If the child still cannot be confirmed stopped, report the conversion as blocked instead of writing concurrently.

The parent may perform unrelated read-only work while waiting, but it must not begin S1 structure work or use uncertified conversion content.

### Handoff rule

The parent may become the conversion executor only when one of these is true:

- no child agent was available from the start; or
- the child has reached a final failed/interrupted status; or
- interruption/closure has been confirmed and the parent explicitly resumes from the last complete segment checkpoint.

On handoff, preserve completed segment checkpoints, inspect the last review record, and continue from the first incomplete segment. Never redo or overwrite completed child work without a source-backed reason. Once handed off, the parent must finish the same `$pdf-to-markdown` gates before S1 consumes the result.

After child success, wait for its final agent status before running the independent completion verifier. Natural-language progress or success messages never replace the on-disk certificate.

The progress probe is read-only evidence. It never grants ownership, finalizes the child workflow, or shortens the two-interval handoff rule.

## Gate 1: Conversion Certificate

Before reading converted Markdown, run:

```powershell
python <pdf-to-markdown-skill>\scripts\verify_completion.py --work-dir <cache-directory>
```

The verifier must confirm:

- `completion.json.status` is `complete`
- source PDF and final Markdown SHA-256 values match current files
- the final Markdown is the ordered merge of current verified segments
- every visual review is passed with zero unresolved items
- recorded page coverage includes every source PDF page

Any verifier failure stops S1 before it writes question-bank artifacts.

## Gate 2: S1 Structure

Before writing `10_题库/`, check:

- every question has a stable anchor
- figures that matter to the question are preserved or linked
- formulas render in Markdown/LaTeX
- `chapter` and `question_type` tags come from `_标签库.md`
- uncertain OCR or figure recognition is explicitly marked for user confirmation
