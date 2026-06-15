from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import probe_pdf_progress as probe


class ProbePdfProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.work = Path(self.temp.name)
        (self.work / "reports" / "visual_review" / "reviews").mkdir(parents=True)
        (self.work / "workflow_state.json").write_text(
            json.dumps({"run_id": "run-1", "status": "awaiting_visual_review", "updated_at": "2026-01-01T00:00:00Z"}),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_checkpoint_progress_and_no_progress(self):
        before = probe.build_snapshot(self.work)
        progressed, _ = probe.compare_snapshots(before, probe.build_snapshot(self.work))
        self.assertFalse(progressed)
        review = self.work / "reports" / "visual_review" / "reviews" / "segment-001.json"
        review.write_text(
            json.dumps({"segment_number": 1, "status": "passed", "pages_reviewed": [1, 2], "reviewed_at": "2026-01-01T01:00:00Z"}),
            encoding="utf-8",
        )
        after = probe.build_snapshot(self.work)
        progressed, reasons = probe.compare_snapshots(before, after)
        self.assertTrue(progressed)
        self.assertTrue(any("完成分段" in reason for reason in reasons))

    def test_run_id_change_is_not_progress(self):
        before = probe.build_snapshot(self.work)
        after = dict(before, run_id="run-2")
        with self.assertRaises(probe.ProbeError):
            probe.compare_snapshots(before, after)


if __name__ == "__main__":
    unittest.main()
