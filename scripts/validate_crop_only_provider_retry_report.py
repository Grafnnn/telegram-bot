#!/usr/bin/env python3
"""Validate redacted crop-only provider retry 002 report."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_provider_retry_002.json"
REPORT_MD = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_provider_retry_002.md"
EXPECTED_FIXTURES = ["pm001-solid-frontal", "pm001-pattern-boundary"]

SECRET_PATTERNS = [
    re.compile(r"sk-(?:proj|svcacct|admin|org)-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{40,}"),
    re.compile(r"\b(?:OPENAI_API_KEY|BOT_INTERNAL_TOKEN|TELEGRAM_BOT_TOKEN|DATABASE_URL)\s*="),
    re.compile("PRIVATE" + r"\s+KEY"),
    re.compile(r"data:image/[a-zA-Z0-9.+-]+;base64,"),
    re.compile(r"[A-Za-z0-9+/]{160,}={0,2}"),
]


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AssertionError(f"Missing report: {_relative(path)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(f"{_relative(path)} must contain a JSON object.")
    return payload


def _reject_risky_text(path: Path, text: str) -> None:
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("re.compile("):
            continue
        for pattern in SECRET_PATTERNS:
            match = pattern.search(line)
            if match:
                raise AssertionError(
                    f"{_relative(path)}:{line_number} contains forbidden pattern "
                    f"{pattern.pattern!r} near {match.group(0)!r}"
                )


def validate() -> None:
    report = _read_json(REPORT_JSON)
    markdown = REPORT_MD.read_text(encoding="utf-8")

    if report.get("experiment_id") != "crop-only-provider-retry-002":
        raise AssertionError("Unexpected experiment id.")
    if report.get("decision") != "GO_FOR_MORE_CROP_ONLY_TESTING":
        raise AssertionError("Retry 002 decision must remain technical-only GO for more testing.")
    if report.get("target") != "local/dev":
        raise AssertionError("Execution target must remain local/dev.")
    if report.get("provider") != "OpenAI" or report.get("model") != "gpt-image-1":
        raise AssertionError("Provider/model mismatch.")
    if report.get("endpoint") != "/v1/images/edits":
        raise AssertionError("Endpoint mismatch.")
    if report.get("dimension_strategy") != "center_crop_to_crop_aspect_then_resize":
        raise AssertionError("Dimension strategy mismatch.")
    if report.get("actual_provider_generations") != 2:
        raise AssertionError("Expected exactly 2 successful provider generations.")
    if report.get("total_http_requests") != 3:
        raise AssertionError("Total HTTP request count must stay recorded as 3.")

    for key in [
        "full_scene_provider_input_used",
        "real_user_photos_used",
        "staging_prod_env_touched",
        "runtime_bot_behavior_changed",
        "imports_sql_direct_db_writes",
        "secret_or_raw_payload_exposure",
        "raw_provider_payloads_committed",
        "user_facing_rollout_approved",
    ]:
        if report.get(key) is not False:
            raise AssertionError(f"{key} must be false.")

    fixtures = report.get("fixtures")
    if not isinstance(fixtures, list) or [entry.get("fixture_id") for entry in fixtures] != EXPECTED_FIXTURES:
        raise AssertionError("Unexpected fixture list.")
    for entry in fixtures:
        if entry.get("preservation") != "pass":
            raise AssertionError(f"{entry.get('fixture_id')} preservation must pass.")
        if entry.get("dimension_action") != "center_crop_to_crop_aspect_then_resize":
            raise AssertionError(f"{entry.get('fixture_id')} must use explicit reconciliation.")
        if entry.get("mean_delta_protected_region") != 0.0:
            raise AssertionError(f"{entry.get('fixture_id')} mean delta must be 0.0.")
        if entry.get("changed_pixel_percent_protected_region") != 0.0:
            raise AssertionError(f"{entry.get('fixture_id')} changed protected pixels must be 0.0.")
        if entry.get("max_delta_protected_region") != 0:
            raise AssertionError(f"{entry.get('fixture_id')} max delta must be 0.")
        if entry.get("stop_condition") is not None:
            raise AssertionError(f"{entry.get('fixture_id')} stop condition must be null.")

    required_markdown = [
        "Status: `GO_FOR_MORE_CROP_ONLY_TESTING`",
        "Full-scene provider input used: no",
        "User-facing rollout approved: no",
        "It does not approve production rollout",
        "Any next provider/model/prompt expansion still needs a separate capped packet",
    ]
    missing = [phrase for phrase in required_markdown if phrase not in markdown]
    if missing:
        raise AssertionError(f"Missing required markdown text: {', '.join(missing)}")

    _reject_risky_text(REPORT_JSON, json.dumps(report, ensure_ascii=False, sort_keys=True))
    _reject_risky_text(REPORT_MD, markdown)


def main() -> int:
    try:
        validate()
    except AssertionError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print("crop-only provider retry 002 report validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
