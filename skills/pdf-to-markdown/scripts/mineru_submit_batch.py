from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import requests

from mineru_common import (
    API_BASE_URL,
    MAX_BATCH_FILES,
    NETWORK_BACKOFF_SECONDS,
    RETRIABLE_SUBMIT_CODES,
    SUBMIT_RETRY_LIMIT,
    UPLOAD_RETRY_LIMIT,
    MineruResponseError,
    append_history,
    jitter_sleep,
    load_token,
    looks_like_transient_http_error,
    read_json,
    request_json,
    write_json,
)


def upload_file(upload_url: str, file_path: Path, record: dict[str, Any]) -> None:
    for attempt in range(UPLOAD_RETRY_LIMIT):
        record["upload_attempts"] += 1
        try:
            with file_path.open("rb") as handle:
                response = requests.put(upload_url, data=handle, timeout=180)
            if response.status_code == 200:
                record["status"] = "uploaded"
                append_history(record, f"Uploaded chunk to MinerU on attempt {attempt + 1}.")
                return
            response.raise_for_status()
        except Exception as exc:
            if attempt + 1 >= UPLOAD_RETRY_LIMIT or not looks_like_transient_http_error(exc):
                record["status"] = "failed"
                record["error_message"] = f"Upload failed: {exc}"
                append_history(record, record["error_message"])
                raise
            jitter_sleep(NETWORK_BACKOFF_SECONDS[min(attempt, len(NETWORK_BACKOFF_SECONDS) - 1)])


def submit_group(
    token: str,
    records: list[dict[str, Any]],
    *,
    model_version: str,
    language: str,
    enable_formula: bool,
    enable_table: bool,
    is_ocr: bool,
) -> str:
    body = {
        "files": [{"name": Path(record["file_path"]).name, "data_id": record["data_id"]} for record in records],
        "model_version": model_version,
        "language": language,
        "enable_formula": enable_formula,
        "enable_table": enable_table,
        "is_ocr": is_ocr,
    }

    for attempt in range(SUBMIT_RETRY_LIMIT):
        for record in records:
            record["submit_attempts"] += 1
        try:
            payload = request_json(
                "POST",
                f"{API_BASE_URL}/file-urls/batch",
                token=token,
                json_body=body,
            )
            batch_id = payload["data"]["batch_id"]
            file_urls = payload["data"]["file_urls"]
            if len(file_urls) != len(records):
                raise RuntimeError("MinerU returned a different number of upload URLs than requested files.")
            for record, upload_url in zip(records, file_urls):
                record["batch_id"] = batch_id
                record["upload_url"] = upload_url
                record["status"] = "submit-succeeded"
                append_history(record, f"Received upload URL in batch {batch_id}.")
            for record, upload_url in zip(records, file_urls):
                upload_file(upload_url, Path(record["file_path"]), record)
            return batch_id
        except MineruResponseError as exc:
            retriable = exc.code in RETRIABLE_SUBMIT_CODES
            for record in records:
                record["error_code"] = exc.code
                record["error_message"] = exc.message
                append_history(record, f"Submit attempt failed: {exc}")
            if attempt + 1 >= SUBMIT_RETRY_LIMIT or not retriable:
                raise
            jitter_sleep(NETWORK_BACKOFF_SECONDS[min(attempt, len(NETWORK_BACKOFF_SECONDS) - 1)])
        except Exception as exc:
            for record in records:
                record["error_message"] = str(exc)
                append_history(record, f"Submit/upload exception: {exc}")
            if attempt + 1 >= SUBMIT_RETRY_LIMIT or not looks_like_transient_http_error(exc):
                raise
            jitter_sleep(NETWORK_BACKOFF_SECONDS[min(attempt, len(NETWORK_BACKOFF_SECONDS) - 1)])
    raise RuntimeError("Submit group exhausted all retries.")


def submit_manifest(
    manifest_path: Path,
    *,
    model_version: str,
    language: str,
    enable_formula: bool,
    enable_table: bool,
    is_ocr: bool,
    token: str | None = None,
) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    active = [
        record
        for record in manifest["chunks"]
        if record["status"] in {"prepared", "retry-pending"}
    ]
    if not active:
        return manifest

    api_token = load_token(token)
    for index in range(0, len(active), MAX_BATCH_FILES):
        group = active[index : index + MAX_BATCH_FILES]
        submit_group(
            api_token,
            group,
            model_version=model_version,
            language=language,
            enable_formula=enable_formula,
            enable_table=enable_table,
            is_ocr=is_ocr,
        )
    write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit prepared PDF chunks to MinerU and upload them.")
    parser.add_argument("manifest_path", help="Path to the manifest JSON.")
    parser.add_argument("--model-version", default="vlm")
    parser.add_argument("--language", default="ch")
    parser.add_argument("--disable-formula", action="store_true")
    parser.add_argument("--disable-table", action="store_true")
    parser.add_argument("--is-ocr", action="store_true")
    args = parser.parse_args()

    submit_manifest(
        Path(args.manifest_path).expanduser().resolve(),
        model_version=args.model_version,
        language=args.language,
        enable_formula=not args.disable_formula,
        enable_table=not args.disable_table,
        is_ocr=args.is_ocr,
    )
    print(f"Submitted chunks from {args.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
