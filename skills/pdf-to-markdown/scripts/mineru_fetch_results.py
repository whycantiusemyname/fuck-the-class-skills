from __future__ import annotations

import argparse
import subprocess
import zipfile
from pathlib import Path

import requests
from requests import Response

from mineru_common import append_history, ensure_dir, read_json, write_json


REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
    "Accept-Encoding": "identity",
    "Connection": "close",
}
DOWNLOAD_TIMEOUT_SECONDS = 300
NODE_FALLBACK_SCRIPT = r"""
const fs = require('fs');
const http = require('http');
const https = require('https');
const { URL } = require('url');

const sourceUrl = process.argv[1];
const outputPath = process.argv[2];

function download(currentUrl, redirectCount) {
  if (redirectCount > 5) {
    console.error(`Too many redirects while fetching ${sourceUrl}`);
    process.exit(5);
  }

  const client = currentUrl.startsWith('https:') ? https : http;
  const request = client.get(
    currentUrl,
    {
      headers: {
        'User-Agent': 'Mozilla/5.0',
        'Accept': '*/*',
        'Accept-Encoding': 'identity',
        'Connection': 'close',
      },
    },
    (response) => {
      const statusCode = response.statusCode || 0;
      const location = response.headers.location;
      if ([301, 302, 303, 307, 308].includes(statusCode) && location) {
        response.resume();
        const nextUrl = new URL(location, currentUrl).toString();
        download(nextUrl, redirectCount + 1);
        return;
      }

      if (statusCode !== 200) {
        response.resume();
        console.error(`Unexpected status ${statusCode} while fetching ${currentUrl}`);
        process.exit(4);
        return;
      }

      const file = fs.createWriteStream(outputPath);
      response.pipe(file);
      file.on('finish', () => file.close(() => process.exit(0)));
      file.on('error', (error) => {
        console.error(error && error.stack ? error.stack : String(error));
        process.exit(3);
      });
    }
  );

  request.setTimeout(300000, () => {
    request.destroy(new Error(`Timed out while fetching ${currentUrl}`));
  });
  request.on('error', (error) => {
    console.error(error && error.stack ? error.stack : String(error));
    process.exit(2);
  });
}

download(sourceUrl, 0);
"""


def download_with_requests(url: str, zip_path: Path) -> Response:
    with requests.get(
        url,
        headers=REQUEST_HEADERS,
        timeout=DOWNLOAD_TIMEOUT_SECONDS,
        stream=True,
    ) as response:
        response.raise_for_status()
        with zip_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
        return response


def download_with_node(url: str, zip_path: Path) -> None:
    completed = subprocess.run(
        ["node", "-e", NODE_FALLBACK_SCRIPT, url, str(zip_path)],
        capture_output=True,
        text=True,
        timeout=DOWNLOAD_TIMEOUT_SECONDS + 30,
        check=False,
    )
    if completed.returncode != 0:
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        message = stderr or stdout or f"node exited with code {completed.returncode}"
        raise RuntimeError(f"Node fallback failed: {message}")
    if not zip_path.exists() or zip_path.stat().st_size == 0:
        raise RuntimeError("Node fallback completed without producing a non-empty zip file.")


def download_result_zip(url: str, zip_path: Path) -> str:
    errors: list[str] = []
    zip_path.unlink(missing_ok=True)
    try:
        response = download_with_requests(url, zip_path)
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > 0 and zip_path.stat().st_size == 0:
            raise RuntimeError("Python download created an empty file despite a non-empty Content-Length.")
        return "requests"
    except Exception as exc:
        zip_path.unlink(missing_ok=True)
        errors.append(f"requests: {exc}")

    try:
        download_with_node(url, zip_path)
        return "node-fallback"
    except Exception as exc:
        zip_path.unlink(missing_ok=True)
        errors.append(f"node-fallback: {exc}")

    raise RuntimeError(" | ".join(errors))


def fetch_results(manifest_path: Path, results_dir: Path) -> dict:
    manifest = read_json(manifest_path)
    ensure_dir(results_dir)
    for record in manifest["chunks"]:
        if record.get("status") != "done":
            continue
        url = record.get("result_zip_url")
        if not url:
            record["status"] = "failed"
            record["error_message"] = "Chunk is marked done but has no full_zip_url."
            append_history(record, record["error_message"])
            continue

        chunk_dir = ensure_dir(results_dir / record["chunk_id"])
        zip_path = chunk_dir / "result.zip"
        downloader = download_result_zip(url, zip_path)

        extract_dir = ensure_dir(chunk_dir / "extracted")
        with zipfile.ZipFile(zip_path, "r") as archive:
            archive.extractall(extract_dir)

        record["result_zip_path"] = str(zip_path)
        record["result_dir"] = str(extract_dir)
        append_history(
            record,
            f"Downloaded and extracted result zip to {extract_dir} using {downloader}.",
        )
    write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Download and extract MinerU result zips.")
    parser.add_argument("manifest_path", help="Path to the manifest JSON.")
    parser.add_argument("--results-dir", required=True, help="Directory for downloaded result archives.")
    args = parser.parse_args()

    fetch_results(
        Path(args.manifest_path).expanduser().resolve(),
        Path(args.results_dir).expanduser().resolve(),
    )
    print(f"Fetched results for {args.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
