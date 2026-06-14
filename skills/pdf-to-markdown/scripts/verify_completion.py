from __future__ import annotations

import argparse
from pathlib import Path

from pdf_workflow import verify_completion


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a pdf-to-markdown completion certificate and its hashes.")
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()
    completion = verify_completion(Path(args.work_dir).expanduser().resolve())
    print(
        f"Verified complete run {completion['run_id']}: "
        f"{completion['segment_count']} segments, {completion['page_count']} pages."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
