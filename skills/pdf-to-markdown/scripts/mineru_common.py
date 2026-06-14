from __future__ import annotations

import json
import os
import random
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

API_BASE_URL = "https://mineru.net/api/v4"
SAFE_PAGE_LIMIT = 180
SAFE_SIZE_LIMIT_MB = 180
SAFE_SIZE_LIMIT_BYTES = SAFE_SIZE_LIMIT_MB * 1024 * 1024
MAX_BATCH_FILES = 50

RETRIABLE_SUBMIT_CODES = {
    "-10001",
    "-60001",
    "-60007",
    "-60009",
    "-60022",
}
RETRIABLE_PARSE_CODES = {
    "-60008",
    "-60010",
    "-60020",
    "-60021",
    "-60022",
}
SPLIT_REQUIRED_CODES = {
    "-60005",
    "-60006",
}
PERMANENT_CODES = {
    "A0202",
    "A0211",
    "-60002",
    "-60003",
    "-60004",
    "-60011",
    "-60015",
    "-60016",
}

NETWORK_BACKOFF_SECONDS = [2, 8, 20]
PARSE_RETRY_LIMIT = 2
UPLOAD_RETRY_LIMIT = 3
SUBMIT_RETRY_LIMIT = 3


@dataclass
class MineruResponseError(Exception):
    message: str
    code: str | None = None
    trace_id: str | None = None
    status_code: int | None = None

    def __str__(self) -> str:
        parts = [self.message]
        if self.code:
            parts.append(f"code={self.code}")
        if self.status_code:
            parts.append(f"http={self.status_code}")
        if self.trace_id:
            parts.append(f"trace_id={self.trace_id}")
        return ", ".join(parts)


def load_windows_user_env(name: str) -> str:
    if os.name != "nt":
        return ""
    try:
        import winreg
    except ImportError:
        return ""

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
    except OSError:
        return ""

    return str(value).strip()


def load_token(explicit_token: str | None = None) -> str:
    token = explicit_token or os.environ.get("MINERU_API_TOKEN", "").strip()
    if not token:
        token = load_windows_user_env("MINERU_API_TOKEN")
        if token:
            os.environ["MINERU_API_TOKEN"] = token
    if not token:
        raise RuntimeError(
            "MINERU_API_TOKEN is not set. Set it in the current environment, "
            "or on Windows save it under the user environment variables so the skill can load it automatically."
        )
    return token


def auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "*/*",
    }


def jitter_sleep(seconds: float) -> None:
    time.sleep(seconds + random.uniform(0, 0.75))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_history(record: dict[str, Any], message: str) -> None:
    history = record.setdefault("history", [])
    history.append({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "message": message})


def slugify_for_data_id(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-._")
    return cleaned or "chunk"


def make_data_id(file_stem: str, start_page: int, end_page: int, attempt: int = 0) -> str:
    stem = slugify_for_data_id(file_stem)
    suffix = uuid.uuid4().hex[:8]
    return f"{stem}_p{start_page:04d}-{end_page:04d}_a{attempt}_{suffix}"


def request_json(
    method: str,
    url: str,
    *,
    token: str,
    json_body: dict[str, Any] | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    response = requests.request(
        method,
        url,
        headers=auth_headers(token),
        json=json_body,
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    code = str(payload.get("code", ""))
    if code and code != "0":
        raise MineruResponseError(
            message=payload.get("msg", "MinerU request failed"),
            code=code,
            trace_id=payload.get("trace_id"),
            status_code=response.status_code,
        )
    return payload


def classify_error(code: str | None, message: str | None) -> str:
    code_text = (code or "").strip()
    message_text = (message or "").strip()
    lowered = message_text.lower()

    if code_text in SPLIT_REQUIRED_CODES:
        return "resplit"
    if code_text in PERMANENT_CODES:
        return "permanent"
    if code_text in RETRIABLE_SUBMIT_CODES or code_text in RETRIABLE_PARSE_CODES:
        return "retry"

    split_markers = [
        "文件大小超出限制",
        "文件页数超过限制",
        "page limit",
        "size limit",
        "页数超过限制",
    ]
    if any(marker in message_text for marker in split_markers):
        return "resplit"

    permanent_markers = [
        "token",
        "文件格式不支持",
        "空文件",
        "找不到任务",
        "没有权限",
        "转换失败",
    ]
    if any(marker in lowered or marker in message_text for marker in permanent_markers):
        return "permanent"

    retry_markers = [
        "服务异常",
        "稍后再试",
        "队列已满",
        "超时",
        "失败",
        "timeout",
        "temporarily unavailable",
    ]
    if any(marker in lowered or marker in message_text for marker in retry_markers):
        return "retry"

    return "unknown"


def looks_like_transient_http_error(exc: Exception) -> bool:
    if isinstance(exc, requests.HTTPError):
        response = exc.response
        return response is not None and 500 <= response.status_code < 600
    return isinstance(exc, (requests.ConnectionError, requests.Timeout))


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
