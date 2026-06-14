from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

from mineru_common import API_BASE_URL, append_history, load_token, read_json, request_json, write_json

ACTIVE_STATES = {"waiting-file", "pending", "running", "converting"}
TERMINAL_STATES = {"done", "failed"}


def update_from_result(record: dict[str, Any], result: dict[str, Any]) -> None:
    state = result.get("state")
    record["task_state"] = state
    record["error_message"] = result.get("err_msg") or record.get("error_message")
    if state == "done":
        record["status"] = "done"
        record["result_zip_url"] = result.get("full_zip_url")
        append_history(record, "MinerU marked the chunk as done.")
    elif state in ACTIVE_STATES:
        record["status"] = "processing"
    elif state == "failed":
        record["status"] = "failed"
        append_history(record, f"MinerU marked the chunk as failed: {record.get('error_message') or 'unknown error'}")


def poll_manifest(
    manifest_path: Path,
    *,
    token: str | None = None,
    sleep_seconds: int = 10,
    timeout_seconds: int = 3600,
) -> dict[str, Any]:
    api_token = load_token(token)
    manifest = read_json(manifest_path)
    batch_ids = sorted({record["batch_id"] for record in manifest["chunks"] if record.get("batch_id")})
    chunk_by_data_id = {record["data_id"]: record for record in manifest["chunks"]}
    chunk_by_name = {Path(record["file_path"]).name: record for record in manifest["chunks"]}

    start = time.time()
    while True:
        all_terminal = True
        for batch_id in batch_ids:
            payload = request_json(
                "GET",
                f"{API_BASE_URL}/extract-results/batch/{batch_id}",
                token=api_token,
            )
            for result in payload["data"].get("extract_result", []):
                record = chunk_by_data_id.get(result.get("data_id")) or chunk_by_name.get(result.get("file_name"))
                if record is None:
                    continue
                update_from_result(record, result)
                if result.get("state") not in TERMINAL_STATES:
                    all_terminal = False
            for record in manifest["chunks"]:
                if record.get("batch_id") == batch_id and record.get("status") not in {"done", "failed"}:
                    all_terminal = False
        write_json(manifest_path, manifest)
        if all_terminal:
            return manifest
        if time.time() - start > timeout_seconds:
            raise TimeoutError(f"Polling timed out after {timeout_seconds} seconds.")
        time.sleep(sleep_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll MinerU batch results and update the manifest.")
    parser.add_argument("manifest_path", help="Path to the manifest JSON.")
    parser.add_argument("--sleep-seconds", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    args = parser.parse_args()

    poll_manifest(
        Path(args.manifest_path).expanduser().resolve(),
        sleep_seconds=args.sleep_seconds,
        timeout_seconds=args.timeout_seconds,
    )
    print(f"Polling completed for {args.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
