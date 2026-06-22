#!/usr/bin/env python3
"""Validate Track B transport retry execution report."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_transport_retry_008.json"
REPORT_MD = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_transport_retry_008.md"
PACKET_JSON = (
    REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_track_b_transport_retry_packet_008.json"
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
    packet = _read_json(PACKET_JSON)
    if not REPORT_MD.is_file():
        raise AssertionError(f"Missing Markdown report: {_relative(REPORT_MD)}")
    report_md = REPORT_MD.read_text(encoding="utf-8")

    if report.get("experiment_id") != "crop-only-track-b-transport-retry-008":
        raise AssertionError("Unexpected experiment id.")
    if report.get("baseline") != "main@18a26cf62e8d68133551a28d3cf7a538636a9378":
        raise AssertionError("Baseline mismatch.")
    if report.get("decision") != "TRANSPORT_RETRY_READY_FOR_OPERATOR_REVIEW":
        raise AssertionError("Unexpected decision.")
    if report.get("stop_condition") is not None:
        raise AssertionError("Stop condition must be absent for this successful transport retry.")
    if report.get("actual_provider_http_requests") != 1:
        raise AssertionError("Actual provider HTTP requests must be 1.")
    if report.get("retry_count") != 0:
        raise AssertionError("Retry count must be 0.")
    if report.get("expected_provider_generations") != 1:
        raise AssertionError("Expected provider generations must be 1.")
    if report.get("max_provider_http_requests") != 2:
        raise AssertionError("Max provider HTTP requests must be 2.")
    if report.get("fixture_scope") != ["pm001-solid-frontal"]:
        raise AssertionError("Fixture scope must remain one fixture.")
    if report.get("input_scope") != "crop_source + crop_mask + fabric_reference only":
        raise AssertionError("Input scope must remain crop-only.")
    if packet.get("max_provider_http_requests_after_go") != report.get("max_provider_http_requests"):
        raise AssertionError("Report cap must match packet cap.")

    fixtures = report.get("fixtures")
    if not isinstance(fixtures, list) or len(fixtures) != 1:
        raise AssertionError("Report must contain exactly one completed fixture.")
    fixture = fixtures[0]
    if fixture.get("fixture_id") != "pm001-solid-frontal":
        raise AssertionError("Unexpected completed fixture.")
    if fixture.get("preservation") != "pass":
        raise AssertionError("Transport retry fixture must pass preservation.")
    if fixture.get("provider_output_dimensions") != {"width": 1024, "height": 1536}:
        raise AssertionError("Provider output dimensions mismatch.")
    if fixture.get("reconciled_crop_dimensions") != {"width": 57, "height": 105}:
        raise AssertionError("Reconciled crop dimensions mismatch.")
    if fixture.get("mean_delta_protected_region") != 0.0:
        raise AssertionError("Mean delta must be 0.0.")
    if fixture.get("changed_pixel_percent_protected_region") != 0.0:
        raise AssertionError("Changed protected pixels must be 0.0.")
    if fixture.get("max_delta_protected_region") != 0:
        raise AssertionError("Max delta must be 0.")

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
    ]:
        _assert_false(report, key)

    required_md_text = [
        "Decision: `TRANSPORT_RETRY_READY_FOR_OPERATOR_REVIEW`",
        "Actual provider HTTP requests | 1",
        "Retry count | 0",
        "Stop condition | none",
        "`pm001-solid-frontal` | pass",
        "It does not approve user-facing Telegram/admin behavior",
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
    print("crop-only Track B transport retry report validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
