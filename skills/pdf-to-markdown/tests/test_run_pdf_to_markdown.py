from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from run_pdf_to_markdown import export_single_chunk_passthrough


class SingleChunkPassthroughTests(unittest.TestCase):
    def make_manifest(self, root: Path, result_dir: Path) -> Path:
        manifest_path = root / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "source_pdf": str(root / "source.pdf"),
                    "chunks": [
                        {
                            "chunk_id": "pages-0001-0001",
                            "start_page": 1,
                            "end_page": 1,
                            "status": "done",
                            "result_dir": str(result_dir),
                            "history": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return manifest_path

    def test_default_export_is_byte_for_byte_passthrough(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result_dir = root / "result"
            reports_dir = root / "reports"
            result_dir.mkdir()
            reports_dir.mkdir()
            source_bytes = (
                b"\xef\xbb\xbfTitle\r\n"
                b"$F(x)=\\left[\\frac{1}{1+x}\\right]$\r\n"
                b"Plain [bracketed prose] must also stay untouched.\r\n"
            )
            (result_dir / "full.md").write_bytes(source_bytes)
            manifest_path = self.make_manifest(root, result_dir)
            output_md = root / "output.md"

            export_single_chunk_passthrough(manifest_path, output_md, reports_dir)

            self.assertEqual(output_md.read_bytes(), source_bytes)
            report = json.loads((reports_dir / "passthrough_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["content_transform"], "none")

    def test_image_width_does_not_rewrite_math(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result_dir = root / "result"
            reports_dir = root / "reports"
            result_dir.mkdir()
            reports_dir.mkdir()
            math = r"$F(x)=\left[\frac{1}{1+x}\right]$"
            (result_dir / "full.md").write_text(
                f"{math}\n\n![plot](images/plot.png)\n",
                encoding="utf-8",
            )
            manifest_path = self.make_manifest(root, result_dir)
            output_md = root / "output.md"

            export_single_chunk_passthrough(
                manifest_path,
                output_md,
                reports_dir,
                image_width=480,
            )

            output = output_md.read_text(encoding="utf-8")
            self.assertIn(math, output)
            self.assertIn("![[images/plot.png|480]]", output)
            self.assertNotIn("$$$", output)
            report = json.loads((reports_dir / "passthrough_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["content_transform"], "image-width-only")


if __name__ == "__main__":
    unittest.main()
