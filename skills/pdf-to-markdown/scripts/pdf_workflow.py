from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse


WORKFLOW_VERSION = 1
STATE_FILE = "workflow_state.json"
COMPLETION_FILE = "completion.json"
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
OBSIDIAN_IMAGE_RE = re.compile(r"!\[\[([^\]]+)\]\]")
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
HTML_IMAGE_RE = re.compile(r'<img\b[^>]*src=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)
UNRESOLVED_MARKERS = ("CHECK_SOURCE", "CHECK_CROP")


class WorkflowValidationError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def make_run_id(source_pdf: Path, source_sha256: str | None = None) -> str:
    source_sha256 = source_sha256 or sha256_file(source_pdf)
    return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{source_sha256[:12]}-{uuid.uuid4().hex[:8]}"


def state_path(work_dir: Path) -> Path:
    return work_dir / STATE_FILE


def completion_path(work_dir: Path) -> Path:
    return work_dir / COMPLETION_FILE


def load_state(work_dir: Path) -> dict:
    path = state_path(work_dir)
    if not path.exists():
        raise WorkflowValidationError(f"Missing workflow state: {path}")
    return read_json(path)


def write_state(work_dir: Path, state: dict) -> None:
    state["updated_at"] = utc_now()
    atomic_write_json(state_path(work_dir), state)


def reset_postprocessing_artifacts(work_dir: Path) -> None:
    for path in (
        work_dir / "draft.md",
        state_path(work_dir),
        completion_path(work_dir),
        work_dir / "reports" / "llm_readthrough_prompt.txt",
        work_dir / "reports" / "text_repair_validation.json",
    ):
        path.unlink(missing_ok=True)
    for directory in (
        work_dir / "reports" / "llm_readthrough_segments",
        work_dir / "reports" / "visual_review",
        work_dir / "images",
        work_dir / "assets",
    ):
        if directory.exists():
            shutil.rmtree(directory)


def create_workflow_state(
    work_dir: Path,
    *,
    run_id: str,
    source_pdf: Path,
    requested_output: Path,
    draft_md: Path,
    segment_manifest: Path,
    page_count: int,
    status: str = "awaiting_text_repair",
    source_pdf_sha256: str | None = None,
    blockers: list[str] | None = None,
) -> dict:
    current_source_sha256 = sha256_file(source_pdf)
    if source_pdf_sha256 is not None and current_source_sha256 != source_pdf_sha256:
        raise WorkflowValidationError("Source PDF changed while the MinerU preparation run was in progress.")
    state = {
        "workflow_version": WORKFLOW_VERSION,
        "run_id": run_id,
        "status": status,
        "source_pdf": str(source_pdf),
        "source_pdf_sha256": current_source_sha256,
        "page_count": page_count,
        "requested_output": str(requested_output),
        "draft_markdown": str(draft_md),
        "draft_sha256": sha256_file(draft_md) if draft_md.exists() else None,
        "segment_manifest": str(segment_manifest),
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "blockers": blockers or [],
    }
    atomic_write_json(state_path(work_dir), state)
    return state


def image_references(text: str) -> Counter[str]:
    references: list[str] = []
    for match in OBSIDIAN_IMAGE_RE.finditer(text):
        references.append(match.group(1).split("|", 1)[0].strip())
    references.extend(match.group(1).strip() for match in MARKDOWN_IMAGE_RE.finditer(text))
    references.extend(match.group(1).strip() for match in HTML_IMAGE_RE.finditer(text))
    return Counter(references)


def _expected_segment_files(manifest: dict, key: str) -> list[Path]:
    return [Path(segment[key]) for segment in manifest.get("segments", [])]


def _require_exact_files(directory: Path, expected: list[Path], suffix: str) -> None:
    expected_names = {path.name for path in expected}
    actual_names = {path.name for path in directory.glob(f"*{suffix}") if path.is_file()}
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        extra = sorted(actual_names - expected_names)
        raise WorkflowValidationError(f"Segment file mismatch under {directory}; missing={missing}, extra={extra}")


def validate_text_repairs(work_dir: Path) -> dict:
    state = load_state(work_dir)
    if state.get("status") not in {"awaiting_text_repair", "awaiting_visual_review"}:
        raise WorkflowValidationError(f"Text repair validation is invalid from status {state.get('status')!r}.")

    source_pdf = Path(state["source_pdf"])
    draft_md = Path(state["draft_markdown"])
    if sha256_file(source_pdf) != state["source_pdf_sha256"]:
        raise WorkflowValidationError("Source PDF hash no longer matches workflow state.")
    if sha256_file(draft_md) != state["draft_sha256"]:
        raise WorkflowValidationError("Draft Markdown hash no longer matches workflow state.")

    manifest_path = Path(state["segment_manifest"])
    manifest = read_json(manifest_path)
    if manifest.get("run_id") != state["run_id"]:
        raise WorkflowValidationError("Segment manifest belongs to a different run_id.")
    repaired_paths = _expected_segment_files(manifest, "repaired_path")
    _require_exact_files(repaired_paths[0].parent, repaired_paths, ".md")

    validated_segments: list[dict] = []
    for segment in manifest.get("segments", []):
        source_path = Path(segment["source_path"])
        repaired_path = Path(segment["repaired_path"])
        if sha256_file(source_path) != segment["source_sha256"]:
            raise WorkflowValidationError(f"Source segment changed after preparation: {source_path}")
        source_text = source_path.read_text(encoding="utf-8")
        repaired_text = repaired_path.read_text(encoding="utf-8")
        if source_text and not repaired_text:
            raise WorkflowValidationError(f"Repaired segment is unexpectedly empty: {repaired_path}")
        if image_references(source_text) != image_references(repaired_text):
            raise WorkflowValidationError(f"Image references changed during text repair: {repaired_path}")
        repaired_sha256 = sha256_file(repaired_path)
        segment["repaired_sha256"] = repaired_sha256
        validated_segments.append(
            {
                "segment_number": segment["segment_number"],
                "source_sha256": segment["source_sha256"],
                "repaired_sha256": repaired_sha256,
            }
        )

    atomic_write_json(manifest_path, manifest)
    report = {
        "run_id": state["run_id"],
        "status": "passed",
        "validated_at": utc_now(),
        "segment_count": len(validated_segments),
        "segments": validated_segments,
    }
    report_path = work_dir / "reports" / "text_repair_validation.json"
    atomic_write_json(report_path, report)
    state["status"] = "awaiting_visual_review"
    state["text_repair_validation"] = str(report_path)
    state["blockers"] = []
    write_state(work_dir, state)
    return report


def _visual_prompt(state: dict, segment: dict, total_segments: int, visual_manifest: Path) -> str:
    return f"""Verify this repaired Markdown segment against the rendered source PDF pages.

Inputs:
- Source PDF: {state['source_pdf']}
- Rendered page manifest: {visual_manifest}
- Repaired segment: {segment['repaired_path']}
- Verified output: {segment['verified_path']}
- Review record: {segment['review_path']}
- Segment: {segment['segment_number']} / {total_segments}

Protocol:
- Inspect exactly one rendered PDF page at a time.
- Locate this segment by headings, question numbers, boundary sentences, formulas, and tables.
- Start from the previous segment's boundary page when this is not the first segment.
- Check omissions, duplicates, order, numbers, signs, subscripts, superscripts, limits, matrices, question labels, options, tables, figures, and captions.
- Write the corrected complete segment to the verified output. If no correction is needed, still copy it there unchanged.
- Preserve all image references exactly.
- Record every inspected 1-based PDF page number in the review record.
- Use status passed only when unresolved is empty. Otherwise use blocked and do not guess.
- Do not call any fallback or vision-crop skill.
"""


def prepare_visual_review(work_dir: Path, *, dpi: int = 180, reset: bool = False) -> dict:
    state = load_state(work_dir)
    if state.get("status") != "awaiting_visual_review" and not (reset and state.get("status") == "blocked"):
        raise WorkflowValidationError("Validate all repaired segments before preparing visual review.")

    root = work_dir / "reports" / "visual_review"
    manifest_path = root / "manifest.json"
    if manifest_path.exists() and not reset:
        existing = read_json(manifest_path)
        if existing.get("run_id") == state["run_id"]:
            validate_visual_manifest(state)
            return existing
    if root.exists():
        shutil.rmtree(root)

    try:
        import fitz
    except ImportError as exc:
        raise WorkflowValidationError("PyMuPDF is required for visual source verification.") from exc

    pages_dir = root / "pages"
    prompts_dir = root / "prompts"
    verified_dir = root / "verified"
    reviews_dir = root / "reviews"
    for directory in (pages_dir, prompts_dir, verified_dir, reviews_dir):
        directory.mkdir(parents=True, exist_ok=True)

    source_pdf = Path(state["source_pdf"])
    document = fitz.open(source_pdf)
    if document.page_count != state["page_count"]:
        document.close()
        raise WorkflowValidationError("Rendered PDF page count differs from workflow state.")
    page_records: list[dict] = []
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    for index in range(document.page_count):
        page_path = pages_dir / f"page-{index + 1:04d}.png"
        document.load_page(index).get_pixmap(matrix=matrix, alpha=False).save(page_path)
        page_records.append(
            {
                "page_number": index + 1,
                "image_path": str(page_path),
                "sha256": sha256_file(page_path),
            }
        )
    document.close()

    segment_manifest_path = Path(state["segment_manifest"])
    segment_manifest = read_json(segment_manifest_path)
    visual_segments: list[dict] = []
    total_segments = len(segment_manifest.get("segments", []))
    for segment in segment_manifest.get("segments", []):
        number = int(segment["segment_number"])
        verified_path = verified_dir / f"segment-{number:03d}.md"
        review_path = reviews_dir / f"segment-{number:03d}.json"
        prompt_path = prompts_dir / f"segment-{number:03d}.txt"
        segment["verified_path"] = str(verified_path)
        segment["review_path"] = str(review_path)
        prompt_path.write_text(_visual_prompt(state, segment, total_segments, manifest_path), encoding="utf-8")
        atomic_write_json(
            review_path,
            {
                "run_id": state["run_id"],
                "segment_number": number,
                "status": "pending",
                "repaired_sha256": segment.get("repaired_sha256"),
                "verified_sha256": None,
                "pages_reviewed": [],
                "changes": [],
                "unresolved": [],
            },
        )
        visual_segments.append(
            {
                "segment_number": number,
                "repaired_path": segment["repaired_path"],
                "verified_path": str(verified_path),
                "review_path": str(review_path),
                "prompt_path": str(prompt_path),
            }
        )
    atomic_write_json(segment_manifest_path, segment_manifest)

    manifest = {
        "workflow_version": WORKFLOW_VERSION,
        "run_id": state["run_id"],
        "source_pdf": state["source_pdf"],
        "source_pdf_sha256": state["source_pdf_sha256"],
        "page_count": state["page_count"],
        "dpi": dpi,
        "pages": page_records,
        "segments": visual_segments,
    }
    atomic_write_json(manifest_path, manifest)
    state["visual_review_manifest"] = str(manifest_path)
    state["status"] = "awaiting_visual_review"
    state["blockers"] = []
    write_state(work_dir, state)
    return manifest


def validate_visual_manifest(state: dict) -> dict:
    manifest_path_text = state.get("visual_review_manifest")
    if not manifest_path_text:
        raise WorkflowValidationError("Workflow state has no visual review manifest.")
    manifest_path = Path(manifest_path_text)
    if not manifest_path.exists():
        raise WorkflowValidationError(f"Missing visual review manifest: {manifest_path}")
    manifest = read_json(manifest_path)
    if manifest.get("run_id") != state["run_id"]:
        raise WorkflowValidationError("Visual review manifest belongs to a different run.")
    if manifest.get("source_pdf_sha256") != state["source_pdf_sha256"]:
        raise WorkflowValidationError("Visual review manifest source hash mismatch.")
    if int(manifest.get("page_count", -1)) != int(state["page_count"]):
        raise WorkflowValidationError("Visual review manifest page count mismatch.")
    pages = manifest.get("pages", [])
    if [int(page.get("page_number", -1)) for page in pages] != list(range(1, int(state["page_count"]) + 1)):
        raise WorkflowValidationError("Visual review page manifest is incomplete or out of order.")
    for page in pages:
        image_path = Path(page["image_path"])
        if not image_path.exists() or sha256_file(image_path) != page.get("sha256"):
            raise WorkflowValidationError(f"Rendered visual review page is missing or changed: {image_path}")
    return manifest


def parse_page_spec(value: str) -> list[int]:
    pages: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start, end = int(start_text), int(end_text)
            if start > end:
                raise WorkflowValidationError(f"Invalid page range: {part}")
            pages.update(range(start, end + 1))
        else:
            pages.add(int(part))
    return sorted(pages)


def record_visual_review(
    work_dir: Path,
    *,
    segment_number: int,
    pages_reviewed: list[int],
    status: str,
    use_repaired: bool = False,
    changes: list | None = None,
    unresolved: list | None = None,
) -> dict:
    state = load_state(work_dir)
    if state.get("status") not in {"awaiting_visual_review", "blocked"}:
        raise WorkflowValidationError(f"Cannot record visual review from status {state.get('status')!r}.")
    manifest = read_json(Path(state["segment_manifest"]))
    matches = [segment for segment in manifest.get("segments", []) if int(segment["segment_number"]) == segment_number]
    if len(matches) != 1:
        raise WorkflowValidationError(f"Unknown segment number: {segment_number}")
    segment = matches[0]
    repaired_path = Path(segment["repaired_path"])
    verified_path = Path(segment["verified_path"])
    review_path = Path(segment["review_path"])
    if use_repaired:
        shutil.copy2(repaired_path, verified_path)
    if not verified_path.exists():
        raise WorkflowValidationError(f"Missing verified segment: {verified_path}")
    changes = changes or []
    unresolved = unresolved or []
    if status not in {"passed", "blocked"}:
        raise WorkflowValidationError("Visual review status must be passed or blocked.")
    if status == "passed" and unresolved:
        raise WorkflowValidationError("A passed visual review cannot contain unresolved items.")
    if not pages_reviewed:
        raise WorkflowValidationError("Visual review must record at least one PDF page.")
    report = {
        "run_id": state["run_id"],
        "segment_number": segment_number,
        "status": status,
        "repaired_sha256": sha256_file(repaired_path),
        "verified_sha256": sha256_file(verified_path),
        "pages_reviewed": sorted(set(pages_reviewed)),
        "changes": changes,
        "unresolved": unresolved,
        "reviewed_at": utc_now(),
    }
    atomic_write_json(review_path, report)
    return report


def markdown_self_check(text: str) -> dict:
    control_characters = len(CONTROL_CHAR_RE.findall(text))
    latex_issues: list[str] = []
    if "$$$" in text:
        latex_issues.append("triple-dollar delimiter")
    if "\\left$$" in text or "\\right$$" in text:
        latex_issues.append("split left/right delimiter")
    if text.count("\\left") != text.count("\\right"):
        latex_issues.append("unbalanced left/right")
    unresolved = [marker for marker in UNRESOLVED_MARKERS if marker in text]
    return {
        "control_characters": control_characters,
        "latex_issues": latex_issues,
        "unresolved_markers": unresolved,
    }


def _local_image_target(reference: str, base_dir: Path) -> Path | None:
    reference = reference.strip().strip("<>")
    parsed = urlparse(reference)
    if parsed.scheme or reference.startswith("#"):
        return None
    path_text = unquote(reference.split("#", 1)[0])
    return (base_dir / path_text).resolve()


def broken_image_links(text: str, base_dir: Path) -> list[str]:
    broken: list[str] = []
    for reference in image_references(text):
        target = _local_image_target(reference, base_dir)
        if target is not None and not target.exists():
            broken.append(reference)
    return sorted(broken)


def validate_ordered_page_coverage(page_groups: list[list[int]], page_count: int) -> list[int]:
    if not page_groups:
        raise WorkflowValidationError("Visual review contains no segment page ranges.")
    covered: set[int] = set()
    previous_min = 1
    previous_max = 0
    for index, raw_pages in enumerate(page_groups, start=1):
        pages = sorted(set(int(page) for page in raw_pages))
        if not pages:
            raise WorkflowValidationError(f"Visual review segment {index} has no pages.")
        if pages != list(range(pages[0], pages[-1] + 1)):
            raise WorkflowValidationError(f"Visual review segment {index} does not record a contiguous page range.")
        if pages[0] < previous_min or pages[0] > previous_max + 1:
            raise WorkflowValidationError(f"Visual review segment {index} is out of document order.")
        if pages[-1] < previous_max:
            raise WorkflowValidationError(f"Visual review segment {index} moves backward in the PDF.")
        covered.update(pages)
        previous_min = pages[0]
        previous_max = pages[-1]
    expected = list(range(1, page_count + 1))
    if sorted(covered) != expected:
        missing = sorted(set(expected) - covered)
        extra = sorted(covered - set(expected))
        raise WorkflowValidationError(f"PDF page coverage is incomplete; missing={missing}, extra={extra}")
    return expected


def _copy_staged_assets(work_dir: Path, final_parent: Path) -> None:
    for name in ("images", "assets"):
        source = work_dir / name
        if source.exists():
            destination = final_parent / name
            if source.resolve() == destination.resolve():
                continue
            shutil.copytree(source, destination, dirs_exist_ok=True)


def finalize_workflow(work_dir: Path, output_md: Path | None = None) -> dict:
    state = load_state(work_dir)
    try:
        if state.get("status") not in {"awaiting_visual_review", "blocked", "ready_to_finalize"}:
            raise WorkflowValidationError(f"Cannot finalize from status {state.get('status')!r}.")
        source_pdf = Path(state["source_pdf"])
        draft_md = Path(state["draft_markdown"])
        if sha256_file(source_pdf) != state["source_pdf_sha256"]:
            raise WorkflowValidationError("Source PDF hash changed before finalization.")
        if sha256_file(draft_md) != state["draft_sha256"]:
            raise WorkflowValidationError("Draft Markdown hash changed before finalization.")
        validate_visual_manifest(state)

        manifest = read_json(Path(state["segment_manifest"]))
        if manifest.get("run_id") != state["run_id"]:
            raise WorkflowValidationError("Segment manifest belongs to another run.")
        repaired_paths = _expected_segment_files(manifest, "repaired_path")
        verified_paths = _expected_segment_files(manifest, "verified_path")
        review_paths = _expected_segment_files(manifest, "review_path")
        _require_exact_files(repaired_paths[0].parent, repaired_paths, ".md")
        _require_exact_files(verified_paths[0].parent, verified_paths, ".md")
        _require_exact_files(review_paths[0].parent, review_paths, ".json")

        page_groups: list[list[int]] = []
        review_summaries: list[dict] = []
        parts: list[str] = []
        for segment in manifest.get("segments", []):
            repaired_path = Path(segment["repaired_path"])
            verified_path = Path(segment["verified_path"])
            review_path = Path(segment["review_path"])
            if sha256_file(repaired_path) != segment.get("repaired_sha256"):
                raise WorkflowValidationError(f"Repaired segment hash mismatch: {repaired_path}")
            review = read_json(review_path)
            if review.get("run_id") != state["run_id"] or int(review.get("segment_number", -1)) != int(segment["segment_number"]):
                raise WorkflowValidationError(f"Visual review belongs to another run or segment: {review_path}")
            if review.get("status") != "passed" or review.get("unresolved"):
                raise WorkflowValidationError(f"Visual review is not passed: {review_path}")
            if review.get("repaired_sha256") != sha256_file(repaired_path):
                raise WorkflowValidationError(f"Review repaired hash mismatch: {review_path}")
            if review.get("verified_sha256") != sha256_file(verified_path):
                raise WorkflowValidationError(f"Review verified hash mismatch: {review_path}")
            repaired_text = repaired_path.read_text(encoding="utf-8")
            verified_text = verified_path.read_text(encoding="utf-8")
            if image_references(repaired_text) != image_references(verified_text):
                raise WorkflowValidationError(f"Image references changed during visual review: {verified_path}")
            pages = {int(page) for page in review.get("pages_reviewed", [])}
            if not pages or min(pages) < 1 or max(pages) > int(state["page_count"]):
                raise WorkflowValidationError(f"Invalid page coverage in {review_path}")
            page_groups.append(sorted(pages))
            parts.append(verified_text)
            review_summaries.append(
                {
                    "segment_number": segment["segment_number"],
                    "verified_sha256": review["verified_sha256"],
                    "pages_reviewed": sorted(pages),
                    "change_count": len(review.get("changes", [])),
                }
            )

        covered_pages = validate_ordered_page_coverage(page_groups, int(state["page_count"]))

        final_text = "".join(parts)
        self_check = markdown_self_check(final_text)
        if self_check["control_characters"] or self_check["latex_issues"] or self_check["unresolved_markers"]:
            raise WorkflowValidationError(f"Final Markdown self-check failed: {self_check}")

        output_md = (output_md or Path(state["requested_output"])).expanduser().resolve()
        if str(output_md) != str(Path(state["requested_output"]).expanduser().resolve()):
            raise WorkflowValidationError("Final output path differs from the path recorded for this run.")
        output_md.parent.mkdir(parents=True, exist_ok=True)
        staged_broken_links = broken_image_links(final_text, work_dir)
        if staged_broken_links:
            raise WorkflowValidationError(f"Staged Markdown contains broken image links: {staged_broken_links}")
        _copy_staged_assets(work_dir, output_md.parent)
        final_broken_links = broken_image_links(final_text, output_md.parent)
        if final_broken_links:
            raise WorkflowValidationError(f"Final Markdown contains broken image links: {final_broken_links}")

        temporary_output = output_md.with_name(f".{output_md.name}.{uuid.uuid4().hex}.tmp")
        temporary_output.write_text(final_text, encoding="utf-8")
        os.replace(temporary_output, output_md)
        completion = {
            "workflow_version": WORKFLOW_VERSION,
            "run_id": state["run_id"],
            "status": "complete",
            "source_pdf": str(source_pdf),
            "source_pdf_sha256": state["source_pdf_sha256"],
            "page_count": state["page_count"],
            "final_markdown": str(output_md),
            "final_markdown_sha256": sha256_file(output_md),
            "segment_count": len(review_summaries),
            "page_coverage": covered_pages,
            "unresolved_count": 0,
            "segments": review_summaries,
            "self_check": {
                **self_check,
                "broken_image_links": [],
            },
            "completed_at": utc_now(),
        }
        atomic_write_json(completion_path(work_dir), completion)
        state["status"] = "complete"
        state["completion"] = str(completion_path(work_dir))
        state["blockers"] = []
        write_state(work_dir, state)
        return completion
    except (OSError, ValueError, KeyError, WorkflowValidationError) as exc:
        state["status"] = "blocked"
        state["blockers"] = [str(exc)]
        write_state(work_dir, state)
        if isinstance(exc, WorkflowValidationError):
            raise
        raise WorkflowValidationError(str(exc)) from exc


def verify_completion(work_dir: Path) -> dict:
    state = load_state(work_dir)
    path = completion_path(work_dir)
    if not path.exists():
        raise WorkflowValidationError(f"Missing completion certificate: {path}")
    completion = read_json(path)
    if state.get("status") != "complete" or completion.get("status") != "complete":
        raise WorkflowValidationError("Workflow or completion certificate is not complete.")
    if completion.get("run_id") != state.get("run_id"):
        raise WorkflowValidationError("Completion certificate belongs to a different run.")
    source_pdf = Path(completion["source_pdf"])
    final_md = Path(completion["final_markdown"])
    if sha256_file(source_pdf) != completion["source_pdf_sha256"]:
        raise WorkflowValidationError("Source PDF hash does not match completion certificate.")
    if sha256_file(final_md) != completion["final_markdown_sha256"]:
        raise WorkflowValidationError("Final Markdown hash does not match completion certificate.")
    expected_pages = list(range(1, int(completion["page_count"]) + 1))
    if completion.get("page_coverage") != expected_pages:
        raise WorkflowValidationError("Completion certificate does not cover every PDF page.")
    if completion.get("unresolved_count") != 0:
        raise WorkflowValidationError("Completion certificate still contains unresolved issues.")
    if completion.get("segment_count") != len(completion.get("segments", [])):
        raise WorkflowValidationError("Completion segment count is inconsistent.")
    validate_visual_manifest(state)
    manifest = read_json(Path(state["segment_manifest"]))
    if manifest.get("run_id") != completion["run_id"]:
        raise WorkflowValidationError("Current segment manifest belongs to a different run.")
    if len(manifest.get("segments", [])) != completion["segment_count"]:
        raise WorkflowValidationError("Current segment manifest count differs from completion certificate.")
    verified_parts: list[str] = []
    page_groups: list[list[int]] = []
    for segment, summary in zip(manifest.get("segments", []), completion.get("segments", []), strict=True):
        verified_path = Path(segment["verified_path"])
        review = read_json(Path(segment["review_path"]))
        if review.get("run_id") != completion["run_id"] or review.get("status") != "passed" or review.get("unresolved"):
            raise WorkflowValidationError(f"Current visual review is not complete: {segment['review_path']}")
        verified_sha256 = sha256_file(verified_path)
        if verified_sha256 != review.get("verified_sha256") or verified_sha256 != summary.get("verified_sha256"):
            raise WorkflowValidationError(f"Current verified segment hash mismatch: {verified_path}")
        if int(segment["segment_number"]) != int(summary.get("segment_number", -1)):
            raise WorkflowValidationError("Completion segment order differs from the current manifest.")
        verified_parts.append(verified_path.read_text(encoding="utf-8"))
        page_groups.append([int(page) for page in review.get("pages_reviewed", [])])
    validate_ordered_page_coverage(page_groups, int(completion["page_count"]))
    if final_md.read_text(encoding="utf-8") != "".join(verified_parts):
        raise WorkflowValidationError("Final Markdown is not the ordered merge of current verified segments.")
    return completion
