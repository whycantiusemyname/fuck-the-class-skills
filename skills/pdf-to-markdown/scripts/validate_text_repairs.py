from __future__ import annotations

import argparse
from pathlib import Path

from pdf_workflow import validate_text_repairs


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate every repaired LLM readthrough segment.")
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()
    report = validate_text_repairs(Path(args.work_dir).expanduser().resolve())
    print(f"Validated {report['segment_count']} repaired segments.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
