from __future__ import annotations

import argparse
from pathlib import Path

from pdf_workflow import finalize_workflow


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize only fully repaired and visually verified PDF Markdown.")
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--output-md", help="Must match the final path recorded by the MinerU preparation run.")
    args = parser.parse_args()
    completion = finalize_workflow(
        Path(args.work_dir).expanduser().resolve(),
        Path(args.output_md).expanduser().resolve() if args.output_md else None,
    )
    print(f"Finalized {completion['final_markdown']} with completion certificate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
