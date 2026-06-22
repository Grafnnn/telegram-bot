#!/usr/bin/env python3
"""Validate Track B one-fixture retry report."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_one_fixture_retry_011.json"
REPORT_MD = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_one_fixture_retry_011.md"
PACKET_JSON = (
    REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_track_b_one_fixture_retry_packet_011.json"
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


def validate() -> None:
    report = _read_json(REPORT_JSON)
    packet = _read_json(PACKET_JSON)
    if not REPORT_MD.is_file():
        raise AssertionError(f"Missing Markdown report: {_relative(REPORT_MD)}")
    report_md = REPORT_MD.read_text(encoding="utf-8")

    if report.get("experiment_id") != "crop-only-track-b-one-fixture-retry-011":
        raise AssertionError("Unexpected experiment id.")
    if report.get("baseline") != "main@a7254ffe428c7418fad77a601036fcc8ab3dee23":
        raise AssertionError("Baseline mismatch.")
    if report.get("decision") != "HOLD_ONE_FIXTURE_RETRY":
        raise AssertionError("Decision must remain HOLD.")
    if report.get("stop_condition") != "provider_call_failed:ImageGenerationProviderError":
        raise AssertionError("Unexpected stop condition.")
    if report.get("fixture_scope") != packet.get("fixture_ids_after_go"):
        raise AssertionError("Report fixture scope must match packet.")
    if report.get("fixtures") != []:
        raise AssertionError("No fixture should be completed in this HOLD report.")
    if report.get("expected_provider_generations") != 1:
        raise AssertionError("Expected provider generations must remain 1.")
    if report.get("max_provider_http_requests") != 1:
        raise AssertionError("Max provider HTTP requests must remain 1.")
    if report.get("actual_provider_http_requests") != 1:
        raise AssertionError("Actual provider HTTP requests must be 1.")
    if report.get("retry_count") != 0:
        raise AssertionError("Retry count must be 0.")
    if report.get("full_scene_provider_input_used") is not False:
        raise AssertionError("Full-scene provider input must not be used.")

    for key in [
        "provider_outputs_committed",
        "raw_provider_payloads_committed",
        "staging_prod_env_touched",
        "runtime_bot_admin_user_facing_enabled",
        "imports_sql_direct_db_writes",
        "real_user_photos_used",
        "secret_or_raw_payload_exposure",
        "user_facing_rollout_approved",
    ]:
        if report.get(key) is not False:
            raise AssertionError(f"{key} must be false.")

    normalized_md = " ".join(report_md.split())
    required_md_text = [
        "Decision: `HOLD_ONE_FIXTURE_RETRY`",
        "Actual provider HTTP requests | 1",
        "Retry count | 0",
        "Completed fixtures | 0",
        "Stop condition | `provider_call_failed:ImageGenerationProviderError`",
        "No provider output image was produced",
        "User-facing rollout approved: no",
        "A future attempt needs a new issue comment/packet",
    ]
    missing = [phrase for phrase in required_md_text if phrase not in normalized_md]
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
    print("crop-only Track B one-fixture retry report validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
