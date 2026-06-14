# Visual Source Verification

Use this stage only after every segmented LLM repair has passed `validate_text_repairs.py`. Its purpose is to verify the candidate Markdown against the original PDF, not to reconstruct the PDF or crop figures.

## Required Inputs

- `workflow_state.json`
- `reports/llm_readthrough_segments/manifest.json`
- repaired segment files
- `reports/visual_review/manifest.json`
- rendered page images under `reports/visual_review/pages/`
- per-segment prompts under `reports/visual_review/prompts/`

## Segment Loop

For each segment in order:

1. Read the repaired segment completely.
2. Begin at page 1 for the first segment. For later segments, begin at the preceding segment's last reviewed page.
3. Open exactly one rendered PDF page image at a time. Locate the segment by headings, question numbers, boundary sentences, formulas, tables, and figures.
4. Compare content order and every high-risk token: digits, signs, equality/inequality symbols, exponents, subscripts, limits, matrix entries, option labels, table cells, and figure captions.
5. Write a complete verified segment. Do not write a patch or commentary. Preserve image references exactly.
6. Record every inspected page as one contiguous range. Ranges must advance in document order; boundary-page overlap between adjacent segments is valid.
7. Record confirmed changes as a JSON list. If any source difference cannot be decided, record it under `unresolved`, set the review to `blocked`, and stop finalization.

For an unchanged segment, run:

```powershell
python scripts/record_visual_review.py --work-dir <work-dir> --segment 1 --pages 1-12 --status passed --use-repaired
```

For a changed segment, write the complete verified Markdown with a file-writing tool, optionally write a JSON change list, then run:

```powershell
python scripts/record_visual_review.py --work-dir <work-dir> --segment 2 --pages 12-25 --status passed --changes-file <changes.json>
```

## Hard Rules

- Inspect every PDF page; do not sample.
- Never infer unreadable source content.
- Never change image paths.
- Never mark a segment `passed` while `unresolved` is non-empty.
- Never create or edit `completion.json` manually.
- Do not call `$pdf-to-obsidian-notes-vision-crop-with-subagent`, visual reconstruction, OCR fallback, or figure-cropping workflows.
