from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import s3_batch_gate
import s8_digest_gate


class RecoveryGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "课程"
        for name in ("20_知识", "30_我的数据/inbox", "30_我的数据/archive", "90_缓存"):
            (self.root / name).mkdir(parents=True)
        (self.root / "30_我的数据" / "做题记录.md").write_text("# 做题记录\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_s3_resume_after_record_append_before_move(self):
        image = self.root / "30_我的数据" / "inbox" / "a.png"
        image.write_bytes(b"image")
        manifest = s3_batch_gate.prepare(self.root, "batch-1", [image])
        marker = s3_batch_gate.marker("batch-1")
        records = self.root / "30_我的数据" / "做题记录.md"
        records.write_text(records.read_text(encoding="utf-8") + marker + "\n| row |\n", encoding="utf-8")
        s3_batch_gate.mark_recorded(manifest)
        with self.assertRaises(s3_batch_gate.BatchError):
            s3_batch_gate.verify(manifest)
        destination = self.root / "30_我的数据" / "archive" / "a.png"
        image.replace(destination)
        s3_batch_gate.mark_moved(manifest, image, destination)
        s3_batch_gate.finalize(manifest)
        s3_batch_gate.verify(manifest)
        self.assertEqual(records.read_text(encoding="utf-8").count(marker), 1)

    def test_s8_manifest_detects_source_change(self):
        source = self.root / "课件.pdf"
        source.write_bytes(b"source")
        output = self.root / "20_知识" / "第一章.md"
        output.write_text("# 第一章\n", encoding="utf-8")
        manifest = s8_digest_gate.bind(self.root, "第一章", [source], [], [output])
        s8_digest_gate.verify(manifest)
        source.write_bytes(b"changed")
        with self.assertRaises(s8_digest_gate.DigestError):
            s8_digest_gate.verify(manifest)

    def test_s8_completion_must_be_complete(self):
        source = self.root / "课件.pdf"
        source.write_bytes(b"source")
        output = self.root / "20_知识" / "第一章.md"
        output.write_text("# 第一章\n", encoding="utf-8")
        completion = self.root / "90_缓存" / "completion.json"
        completion.write_text(json.dumps({"status": "blocked", "unresolved_count": 1}), encoding="utf-8")
        with self.assertRaises(s8_digest_gate.DigestError):
            s8_digest_gate.bind(self.root, "第一章", [source], [completion], [output])


if __name__ == "__main__":
    unittest.main()
