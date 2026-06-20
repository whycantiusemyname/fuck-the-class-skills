# LLM Readthrough Repair Template

Use this template after `pdf-to-markdown` has already produced:

- the final Markdown note
- one generated prompt file at `reports/llm_readthrough_prompt.txt`
- one segmented readthrough package at `reports/llm_readthrough_segments/`

The goal is broader than the old math-only pass:

- read the whole note by processing all generated segments in order
- repair malformed math so Obsidian can render it
- repair obvious formatting damage caused by PDF parsing
- keep content meaning, section order, image paths, and tables stable

## Inputs

Provide the LLM with:

- `reports/llm_readthrough_prompt.txt`
- `reports/llm_readthrough_segments/manifest.json`
- one `source/segment-XXX.md` file at a time
- the matching `prompts/segment-XXX.txt`

Prefer the generated prompt file as the primary instruction source because it already includes the exact output path and segment package location.

## Repair Rules

The LLM should:

- process every segment in order until the full note has been covered
- fix malformed math delimiters
- fix broken display math blocks, inline math, and obvious unsupported wrappers when the intended math is clear
- clean up obvious formatting glitches from PDF parsing
- keep table structure unchanged unless a tiny local fix is required to keep the row valid
- preserve image paths exactly as written
- preserve surrounding prose unless formatting repair requires a minimal local change

The LLM should not:

- rewrite the chapter structure
- split tables into lists
- rename image paths
- rewrite unrelated paragraphs for style
- invent missing content

## Prompt Template

```text
Repair this Markdown segment for Obsidian readability.

Goals:
- Process all segments in order, one segment at a time.
- Fix malformed math so Obsidian MathJax can render it.
- Clean up obvious formatting damage caused by PDF parsing.
- Preserve the source meaning, section order, tables, images, and links.

Rules:
- Return repaired Markdown for this segment only.
- Preserve image paths exactly as they already appear in the segment.
- Preserve table structure unless a table row is completely invalid; prefer the smallest possible fix.
- Use `$...$` for inline math and `$$ ... $$` for display math.
- Fix unsupported or broken LaTeX wrappers when the intended math is clear.
- Keep wording changes minimal; repair formatting and math before prose.
- Do not invent missing content.

Inputs:
- Global prompt file: <path or pasted content from reports/llm_readthrough_prompt.txt>
- Segment manifest: <path or pasted JSON from reports/llm_readthrough_segments/manifest.json>
- Current segment source: <path or pasted content>
- Current segment prompt: <path or pasted content>

Return the repaired segment Markdown only.
```

## Recommended Usage Pattern

1. Run `pdf-to-markdown`.
2. Open `reports/llm_readthrough_segments/manifest.json`.
3. For each segment in order, pass the source segment plus its matching prompt to the LLM.
4. Save each repaired result into the matching `repaired/segment-XXX.md`.
5. Run `scripts/merge_llm_readthrough_segments.py` to merge repaired segments back into the requested final Markdown file.
6. Run `scripts/write_completion.py --source-pdf <input.pdf> --final-markdown <output.md> --work-dir <work-dir>`.
7. Run `scripts/verify_completion.py --work-dir <work-dir>`.
8. Review the repaired Markdown again in Obsidian if the user wants a human-facing quality check.
