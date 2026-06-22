#!/usr/bin/env python3
"""Validate Track B operator-review execution report."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_operator_review_006.json"
REPORT_MD = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_operator_review_006.md"
READINESS_JSON = (
    REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_track_b_operator_review_readiness_006.json"
)

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
        raise AssertionError(f"Missing JSON file: {_relative(path)}")
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


def _assert_false(report: dict[str, Any], key: str) -> None:
    if report.get(key) is not False:
        raise AssertionError(f"{key} must be false.")


def validate() -> None:
    report = _read_json(REPORT_JSON)
    readiness = _read_json(READINESS_JSON)
    if not REPORT_MD.is_file():
        raise AssertionError(f"Missing Markdown report: {_relative(REPORT_MD)}")
    report_md = REPORT_MD.read_text(encoding="utf-8")

    if report.get("experiment_id") != "crop-only-track-b-operator-review-006":
        raise AssertionError("Unexpected experiment id.")
    if report.get("baseline") != "main@a49e3f71ec01123fde093f2d1b24c898b90757e3":
        raise AssertionError("Baseline mismatch.")
    if report.get("decision") != "HOLD_TRACK_B_OPERATOR_REVIEW":
        raise AssertionError("Track B result must remain HOLD.")
    if report.get("stop_condition") != "provider_call_failed:URLError":
        raise AssertionError("Unexpected stop condition.")
    if report.get("actual_provider_http_requests") != 2:
        raise AssertionError("Actual provider HTTP requests must be 2.")
    if report.get("retry_count") != 1:
        raise AssertionError("Retry count must be 1.")
    if report.get("expected_provider_generations") != 4:
        raise AssertionError("Expected provider generation count must be 4.")
    if report.get("max_provider_http_requests") != 5:
        raise AssertionError("Max provider HTTP requests must be 5.")
    if report.get("fixtures") != []:
        raise AssertionError("No fixtures should be recorded as completed.")
    if report.get("input_scope") != "crop_source + crop_mask + fabric_reference only":
        raise AssertionError("Input scope must remain crop-only.")
    if readiness.get("max_provider_http_requests_after_go") != report.get("max_provider_http_requests"):
        raise AssertionError("Report cap must match readiness cap.")

    for key in [
        "full_scene_provider_input_used",
        "staging_prod_env_touched",
        "runtime_bot_admin_user_facing_enabled",
        "imports_sql_direct_db_writes",
        "real_user_photos_used",
        "secret_or_raw_payload_exposure",
        "raw_provider_payloads_committed",
        "provider_outputs_committed",
        "user_facing_rollout_approved",
        "manual_operator_review_completed",
    ]:
        _assert_false(report, key)

    required_md_text = [
        "Decision: `HOLD_TRACK_B_OPERATOR_REVIEW`",
        "Actual provider HTTP requests | 2",
        "Retry count | 1",
        "Stop condition | `provider_call_failed:URLError`",
        "No fixture completed",
        "Any retry or new Track B execution requires a fresh explicit GO packet.",
    ]
    missing = [phrase for phrase in required_md_text if phrase not in report_md]
    if missing:
        raise AssertionError(f"Markdown report missing required text: {', '.join(missing)}")

    _reject_risky_text(REPORT_JSON, json.dumps(report, ensure_ascii=False, sort_keys=True))
    _reject_risky_text(REPORT_MD, report_md)


def main() -> int:
    try:
        validate()
    except AssertionError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print("crop-only Track B operator review report validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
