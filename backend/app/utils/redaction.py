"""Helpers for safe diagnostic output."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

REDACTED = "[REDACTED]"
BINARY_REDACTED = "[BINARY REDACTED]"

SENSITIVE_KEY_FRAGMENTS = (
    "authorization",
    "x-bot-token",
    "token",
    "secret",
    "password",
    "api-key",
    "api_key",
    "apikey",
)

_HEADER_VALUE_RE = re.compile(r"(?i)\b(authorization|x-bot-token)\s*[:=]\s*(bearer\s+)?[^\s,;]+")
_KEY_VALUE_RE = re.compile(r"(?i)\b([a-z0-9_-]*(?:token|secret|password|api[_-]?key)[a-z0-9_-]*)\s*[:=]\s*[^\s,;]+")
_URL_PASSWORD_RE = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://[^:\s/@]+):[^@\s/]+@")
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_DATA_URI_RE = re.compile(r"(?i)data:image/[a-z0-9.+-]+;base64,[A-Za-z0-9+/=]+")
_UPLOAD_PATH_RE = re.compile(r"(?i)(?:[A-Za-z]:)?(?:/[^\s,;:]+)*/uploads/[^\s,;]+")
_LONG_BASE64_RE = re.compile(r"\b[A-Za-z0-9+/]{80,}={0,2}\b")
_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_LONG_NUMBER_RE = re.compile(r"\b\d{5,}\b")


def _normalized_key(key: object) -> str:
    return str(key).strip().lower().replace("_", "-")


def is_sensitive_key(key: object) -> bool:
    normalized = _normalized_key(key)
    return any(fragment.replace("_", "-") in normalized for fragment in SENSITIVE_KEY_FRAGMENTS)


def sanitize_log_message(value: object) -> str:
    text = str(value)
    text = _URL_PASSWORD_RE.sub(lambda match: f"{match.group(1)}:{REDACTED}@", text)
    text = _DATA_URI_RE.sub("data:image/[REDACTED]", text)
    text = _UPLOAD_PATH_RE.sub("/uploads/[REDACTED_PATH]", text)
    text = _HEADER_VALUE_RE.sub(lambda match: f"{match.group(1)}: {REDACTED}", text)
    text = _KEY_VALUE_RE.sub(lambda match: f"{match.group(1)}={REDACTED}", text)
    text = _BEARER_RE.sub(f"Bearer {REDACTED}", text)
    return _LONG_BASE64_RE.sub(REDACTED, text)


def redact_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return redact_mapping(value)
    if isinstance(value, str):
        return sanitize_log_message(value)
    if isinstance(value, bytes | bytearray | memoryview):
        return BINARY_REDACTED
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, set):
        return {redact_value(item) for item in value}
    return value


def redact_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in values.items():
        key_text = str(key)
        redacted[key_text] = REDACTED if is_sensitive_key(key_text) else redact_value(value)
    return redacted


def safe_exception_summary(exc: Exception) -> str:
    message = sanitize_log_message(str(exc)).strip()
    if not message:
        return exc.__class__.__name__
    return f"{exc.__class__.__name__}: {message}"


def safe_path_for_log(path: str) -> str:
    path_without_query = path.split("?", 1)[0]
    path_without_ids = _UUID_RE.sub("{uuid}", path_without_query)
    path_without_ids = _LONG_NUMBER_RE.sub("{id}", path_without_ids)
    return sanitize_log_message(path_without_ids)
