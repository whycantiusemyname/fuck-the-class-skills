from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import s1_intake_gate as gate


class S1IntakeGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "课程"
        (self.root / "10_题库").mkdir(parents=True)
        (self.root / "90_缓存" / "pdf-to-markdown" / "卷").mkdir(parents=True)
        (self.root / "10_题库" / "_标签库.md").write_text(
            "# 标签库\n\n| 章节 | 能力主题 | 标准知识点标签 | 题数 |\n"
            "|---|---|---|---:|\n| 第一章 | 主题A | `标签A` | 1 |\n",
            encoding="utf-8",
        )
        self.source = self.root / "卷.pdf"
        self.source.write_bytes(b"pdf-source")
        self.final = self.root / "90_缓存" / "pdf-to-markdown" / "卷" / "卷.verified.md"
        self.final.write_text("# 认证文本\n", encoding="utf-8")
        self.completion = self.final.parent / "completion.json"
        self.write_completion(self.source, self.final, self.completion)
        self.output = self.root / "10_题库" / "卷_题面整理.md"
        self.output.write_text(
            "## 卷\n\n%%\nchapter: 综合\nquestion_type: 真题整卷｜期末\n"
            "source: 2024-2025期末\npaper_type: 期末\nacademic_year: 2024-2025\n%%\n\n"
            "### 24-25期末-选1\n\n%%\nchapter: 第一章\nquestion_type: 标签A\n"
            "source: 2024-2025期末\nquestion_form: 选择题\nocr_status: 已对照 PDF 复核\n%%\n\n题面\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def write_completion(source: Path, final: Path, completion: Path):
        payload = {
            "status": "complete",
            "source_pdf": str(source.resolve()),
            "source_pdf_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "final_markdown": str(final.resolve()),
            "final_markdown_sha256": hashlib.sha256(final.read_bytes()).hexdigest(),
            "unresolved_count": 0,
        }
        completion.write_text(json.dumps(payload), encoding="utf-8")

    def test_bind_and_detect_modified_output(self):
        manifest = gate.bind_manifest(
            self.root, self.source, self.completion, [self.output], run_external=False
        )
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertFalse(Path(payload["source"]["path"]).is_absolute())
        self.assertIn(hashlib.sha256(self.source.read_bytes()).hexdigest()[:8], str(manifest))
        gate.verify_manifest(manifest)
        self.output.write_text(self.output.read_text(encoding="utf-8") + "变化\n", encoding="utf-8")
        with self.assertRaises(gate.IntakeError):
            gate.verify_manifest(manifest)

    def test_rejects_draft_and_mineru_paths(self):
        for name in ("draft.md", "卷.mineru.md"):
            with self.subTest(name=name):
                final = self.final.parent / name
                final.write_text("草稿\n", encoding="utf-8")
                completion = self.final.parent / f"{name}.json"
                self.write_completion(self.source, final, completion)
                with self.assertRaises(gate.IntakeError):
                    gate.bind_manifest(
                        self.root, self.source, completion, [self.output], run_external=False
                    )

    def test_rejects_duplicate_source_hash(self):
        gate.bind_manifest(self.root, self.source, self.completion, [self.output], run_external=False)
        source2 = self.root / "卷副本.pdf"
        source2.write_bytes(self.source.read_bytes())
        work2 = self.root / "90_缓存" / "pdf-to-markdown" / "卷副本"
        work2.mkdir()
        final2 = work2 / "卷副本.verified.md"
        final2.write_text("# 认证文本2\n", encoding="utf-8")
        completion2 = work2 / "completion.json"
        self.write_completion(source2, final2, completion2)
        with self.assertRaises(gate.IntakeError):
            gate.bind_manifest(self.root, source2, completion2, [self.output], run_external=False)

    def test_rejects_completion_hash_mismatch(self):
        self.final.write_text("被修改\n", encoding="utf-8")
        with self.assertRaises(gate.IntakeError):
            gate.bind_manifest(self.root, self.source, self.completion, [self.output], run_external=False)


if __name__ == "__main__":
    unittest.main()
