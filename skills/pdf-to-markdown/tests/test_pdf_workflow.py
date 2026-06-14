from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from pdf_workflow import (
    WorkflowValidationError,
    create_workflow_state,
    finalize_workflow,
    prepare_visual_review,
    record_visual_review,
    validate_ordered_page_coverage,
    validate_text_repairs,
    verify_completion,
)
from prepare_llm_readthrough_segments import prepare_segments
import run_pdf_to_markdown as runner


class PdfWorkflowGateTests(unittest.TestCase):
    def create_pdf(self, path: Path, page_count: int = 2) -> None:
        import fitz

        document = fitz.open()
        for index in range(page_count):
            page = document.new_page()
            page.insert_text((72, 72), f"Page {index + 1}")
        document.save(path)
        document.close()

    def prepare_run(self, root: Path) -> tuple[Path, Path, Path]:
        source_pdf = root / "source.pdf"
        draft_md = root / "draft.md"
        final_md = root / "final.md"
        self.create_pdf(source_pdf)
        images_dir = root / "images"
        images_dir.mkdir()
        (images_dir / "plot.png").write_bytes(b"test-image")
        draft_md.write_text("# Paper\n\nQuestion 1: $x^2$.\n\n![[images/plot.png]]\n", encoding="utf-8")
        run_id = "test-run"
        segment_dir = root / "reports" / "llm_readthrough_segments"
        prepare_segments(draft_md, segment_dir, run_id=run_id)
        create_workflow_state(
            root,
            run_id=run_id,
            source_pdf=source_pdf,
            requested_output=final_md,
            draft_md=draft_md,
            segment_manifest=segment_dir / "manifest.json",
            page_count=2,
        )
        return source_pdf, draft_md, final_md

    def test_missing_repaired_segment_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.prepare_run(root)

            with self.assertRaises(WorkflowValidationError):
                validate_text_repairs(root)

            self.assertFalse((root / "completion.json").exists())

    def test_extra_stale_repaired_segment_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.prepare_run(root)
            segment_dir = root / "reports" / "llm_readthrough_segments"
            source_segment = next((segment_dir / "source").glob("*.md"))
            repaired_segment = segment_dir / "repaired" / source_segment.name
            shutil.copy2(source_segment, repaired_segment)
            (segment_dir / "repaired" / "segment-999.md").write_text("stale run output\n", encoding="utf-8")

            with self.assertRaises(WorkflowValidationError):
                validate_text_repairs(root)

    def test_blocked_mineru_run_cannot_enter_text_repair(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.prepare_run(root)
            from pdf_workflow import atomic_write_json, read_json

            state_path = root / "workflow_state.json"
            state = read_json(state_path)
            state["status"] = "blocked"
            state["blockers"] = ["MinerU final failure"]
            atomic_write_json(state_path, state)

            with self.assertRaises(WorkflowValidationError):
                validate_text_repairs(root)

    def test_visual_page_ranges_must_be_contiguous_and_ordered(self) -> None:
        self.assertEqual(validate_ordered_page_coverage([[1, 2], [2, 3]], 3), [1, 2, 3])
        with self.assertRaises(WorkflowValidationError):
            validate_ordered_page_coverage([[2, 3], [1, 2]], 3)
        with self.assertRaises(WorkflowValidationError):
            validate_ordered_page_coverage([[1, 3]], 3)

    def test_full_gate_rejects_incomplete_coverage_then_finalizes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, _, final_md = self.prepare_run(root)
            segment_dir = root / "reports" / "llm_readthrough_segments"
            source_segment = next((segment_dir / "source").glob("*.md"))
            repaired_segment = segment_dir / "repaired" / source_segment.name
            shutil.copy2(source_segment, repaired_segment)

            validate_text_repairs(root)
            visual = prepare_visual_review(root, dpi=72)
            self.assertEqual(visual["page_count"], 2)
            record_visual_review(
                root,
                segment_number=1,
                pages_reviewed=[1],
                status="passed",
                use_repaired=True,
            )

            with self.assertRaises(WorkflowValidationError):
                finalize_workflow(root)
            self.assertFalse(final_md.exists())

            record_visual_review(
                root,
                segment_number=1,
                pages_reviewed=[1, 2],
                status="passed",
                use_repaired=True,
            )
            completion = finalize_workflow(root)
            self.assertEqual(completion["status"], "complete")
            self.assertTrue(final_md.exists())
            self.assertEqual(verify_completion(root)["run_id"], "test-run")

            rendered_page = root / "reports" / "visual_review" / "pages" / "page-0001.png"
            rendered_bytes = rendered_page.read_bytes()
            rendered_page.write_bytes(b"changed")
            with self.assertRaises(WorkflowValidationError):
                verify_completion(root)
            rendered_page.write_bytes(rendered_bytes)

            final_md.write_text("tampered\n", encoding="utf-8")
            with self.assertRaises(WorkflowValidationError):
                verify_completion(root)

    def test_stale_visual_review_run_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.prepare_run(root)
            segment_dir = root / "reports" / "llm_readthrough_segments"
            source_segment = next((segment_dir / "source").glob("*.md"))
            repaired_segment = segment_dir / "repaired" / source_segment.name
            shutil.copy2(source_segment, repaired_segment)

            validate_text_repairs(root)
            prepare_visual_review(root, dpi=72)
            record_visual_review(
                root,
                segment_number=1,
                pages_reviewed=[1, 2],
                status="passed",
                use_repaired=True,
            )

            from pdf_workflow import atomic_write_json, read_json

            review_path = root / "reports" / "visual_review" / "reviews" / "segment-001.json"
            review = read_json(review_path)
            review["run_id"] = "old-run"
            atomic_write_json(review_path, review)

            with self.assertRaises(WorkflowValidationError):
                finalize_workflow(root)

    def test_changed_image_reference_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.prepare_run(root)
            segment_dir = root / "reports" / "llm_readthrough_segments"
            source_segment = next((segment_dir / "source").glob("*.md"))
            source_segment.write_text("![[images/source.png]]\n", encoding="utf-8")
            manifest_path = segment_dir / "manifest.json"
            from pdf_workflow import atomic_write_json, read_json, sha256_file

            manifest = read_json(manifest_path)
            manifest["segments"][0]["source_sha256"] = sha256_file(source_segment)
            atomic_write_json(manifest_path, manifest)
            repaired_segment = segment_dir / "repaired" / source_segment.name
            repaired_segment.write_text("![[images/renamed.png]]\n", encoding="utf-8")

            with self.assertRaises(WorkflowValidationError):
                validate_text_repairs(root)

    def test_runner_stages_draft_without_creating_final_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_pdf = root / "source.pdf"
            final_md = root / "requested-final.md"
            work_dir = root / "work"
            result_dir = root / "mineru-result"
            result_dir.mkdir()
            (result_dir / "full.md").write_text("# MinerU draft\n", encoding="utf-8")
            self.create_pdf(source_pdf, page_count=1)

            def fake_prepare_chunks(_input_pdf, _chunks_dir, manifest_path, **_kwargs):
                manifest_path.parent.mkdir(parents=True, exist_ok=True)
                manifest_path.write_text(
                    "{\n"
                    f'  "source_pdf": "{str(source_pdf).replace(chr(92), chr(92) * 2)}",\n'
                    '  "chunks_dir": "unused",\n'
                    '  "chunks": [{\n'
                    '    "chunk_id": "p0001-0001",\n'
                    '    "start_page": 1,\n'
                    '    "end_page": 1,\n'
                    '    "page_count": 1,\n'
                    '    "status": "done",\n'
                    f'    "result_dir": "{str(result_dir).replace(chr(92), chr(92) * 2)}",\n'
                    '    "history": []\n'
                    '  }]\n'
                    '}\n',
                    encoding="utf-8",
                )

            with mock.patch.object(runner, "prepare_chunks", side_effect=fake_prepare_chunks), mock.patch.object(
                runner, "fetch_results"
            ):
                result = runner.run_pipeline(source_pdf, final_md, work_dir)

            self.assertEqual(result, 3)
            self.assertFalse(final_md.exists())
            self.assertEqual((work_dir / "draft.md").read_text(encoding="utf-8"), "# MinerU draft\n")
            self.assertEqual((work_dir / "workflow_state.json").exists(), True)


if __name__ == "__main__":
    unittest.main()
