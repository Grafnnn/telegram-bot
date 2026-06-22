#!/usr/bin/env python3
"""Validate Track B provider-failure diagnostic packet."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKET_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_track_b_provider_failure_diagnostic_packet_010.md"
MANIFEST_JSON = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "fixtures"
    / "crop_only_track_b_provider_failure_diagnostic_packet_010.json"
)
PARENT_REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_remaining_fixtures_009.json"
FIXTURE_MANIFEST_JSON = (
    REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_visual_quality_expansion_manifest_003.json"
)
EXPECTED_FIXTURE_IDS = [
    "pm001-pattern-boundary",
    "pm003-large-pattern-scale",
    "pm004-edge-boundary-stress",
]

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


def _assert_false(manifest: dict[str, Any], key: str) -> None:
    if manifest.get(key) is not False:
        raise AssertionError(f"{key} must be false.")


def validate() -> None:
    if not PACKET_MD.is_file():
        raise AssertionError(f"Missing packet: {_relative(PACKET_MD)}")
    packet = PACKET_MD.read_text(encoding="utf-8")
    manifest = _read_json(MANIFEST_JSON)
    parent = _read_json(PARENT_REPORT_JSON)
    fixture_manifest = _read_json(FIXTURE_MANIFEST_JSON)

    if parent.get("decision") != "HOLD_REMAINING_FIXTURES_REVIEW":
        raise AssertionError("Parent report must be HOLD.")
    if parent.get("stop_condition") != "provider_call_failed:ImageGenerationProviderError":
        raise AssertionError("Parent report must record provider failure.")
    if parent.get("actual_provider_http_requests") != 2:
        raise AssertionError("Parent report must record two HTTP requests.")
    if parent.get("retry_count") != 1:
        raise AssertionError("Parent report must record one retry.")
    if parent.get("fixtures") != []:
        raise AssertionError("Parent report must have no completed fixtures.")

    if manifest.get("manifest_id") != "crop-only-track-b-provider-failure-diagnostic-packet-010":
        raise AssertionError("Unexpected manifest id.")
    if manifest.get("status") != "provider_failure_diagnostic_packet_not_approved_for_provider_execution":
        raise AssertionError("Manifest must remain not approved for provider execution.")
    if manifest.get("baseline_commit") != "0a4b1d9d97f19458078b98493042606a6b298b70":
        raise AssertionError("Baseline mismatch.")
    if manifest.get("experiment_id") != "crop-only-track-b-provider-failure-diagnostic-010":
        raise AssertionError("Unexpected experiment id.")
    if manifest.get("future_zero_call_target") != "local/dev provider failure diagnostics":
        raise AssertionError("Unexpected diagnostic target.")
    if manifest.get("diagnostic_fixture_ids") != EXPECTED_FIXTURE_IDS:
        raise AssertionError("Diagnostic fixture scope mismatch.")
    if manifest.get("diagnostic_provider_calls_allowed") is not False:
        raise AssertionError("Diagnostics must not allow provider calls.")
    if manifest.get("diagnostic_network_calls_allowed") is not False:
        raise AssertionError("Diagnostics must not allow network calls.")

    for key in [
        "provider_openai_calls_allowed",
        "controlled_provider_execution_allowed",
        "staging_prod_env_allowed",
        "runtime_enablement_allowed",
        "telegram_bot_enablement_allowed",
        "admin_user_facing_enablement_allowed",
        "user_facing_rollout_allowed",
        "visual_quality_approval_allowed",
        "real_user_photos_allowed",
        "imports_sql_direct_db_writes_allowed",
    ]:
        _assert_false(manifest, key)

    retry = manifest.get("future_retry_candidate_after_separate_go")
    if not isinstance(retry, dict):
        raise AssertionError("Missing future retry candidate.")
    if retry.get("fixture_ids") != ["pm001-pattern-boundary"]:
        raise AssertionError("Future retry candidate must be one fixture only.")
    if retry.get("expected_provider_generations") != 1:
        raise AssertionError("Future retry candidate generation cap must be 1.")
    if retry.get("max_provider_http_requests") != 1:
        raise AssertionError("Future retry candidate HTTP cap must be 1.")
    if retry.get("retry_count") != 0:
        raise AssertionError("Future retry candidate must not allow retry.")
    if retry.get("full_scene_person_input_allowed") is not False:
        raise AssertionError("Future retry candidate must forbid full-scene input.")

    fixture_by_id = {
        fixture.get("fixture_id"): fixture
        for fixture in fixture_manifest.get("fixtures", [])
        if isinstance(fixture, dict)
    }
    for fixture_id in EXPECTED_FIXTURE_IDS:
        fixture = fixture_by_id.get(fixture_id)
        if not isinstance(fixture, dict):
            raise AssertionError(f"Missing diagnostic fixture: {fixture_id}")
        for field in ["crop_source", "crop_mask", "fabric_reference"]:
            reference = fixture.get(field)
            if not isinstance(reference, str):
                raise AssertionError(f"{fixture_id} missing {field}.")
            if not (REPO_ROOT / reference).is_file():
                raise AssertionError(f"{fixture_id} {field} does not exist: {reference}")

    required_zero_call_checks = set(manifest.get("required_zero_call_checks", []))
    for check in [
        "fixture_paths_exist",
        "crop_mask_has_editable_transparent_region",
        "crop_source_and_mask_dimensions_match",
        "sanitized_request_shape_built",
        "full_scene_provider_input_absent",
    ]:
        if check not in required_zero_call_checks:
            raise AssertionError(f"Missing zero-call check: {check}")

    required_stop_conditions = set(manifest.get("required_stop_conditions", []))
    for condition in [
        "zero_call_diagnostics_missing",
        "request_shape_would_expose_secret_or_raw_payload",
        "full_scene_person_input_selected",
        "retry_without_new_explicit_gate",
        "staging_production_real_user_photo_imports_sql_or_direct_db_writes_involved",
    ]:
        if condition not in required_stop_conditions:
            raise AssertionError(f"Missing stop condition: {condition}")

    required_packet_text = [
        "Status: `PROVIDER_FAILURE_DIAGNOSTIC_PACKET / NOT APPROVED FOR PROVIDER EXECUTION`",
        "Provider/OpenAI calls: `BLOCKED`",
        "Staging/prod/env changes: `BLOCKED`",
        "Runtime/bot/admin behavior changes: `BLOCKED`",
        "User-facing rollout: `BLOCKED`",
        "run only zero-call diagnostics",
        "max provider HTTP requests: 1",
        "retry count: 0",
        "Any provider retry requires a new fresh explicit GO.",
    ]
    normalized_packet = " ".join(packet.split())
    missing = [phrase for phrase in required_packet_text if phrase not in normalized_packet]
    if missing:
        raise AssertionError(f"Packet missing required text: {', '.join(missing)}")

    _reject_risky_text(PACKET_MD, packet)
    _reject_risky_text(MANIFEST_JSON, json.dumps(manifest, ensure_ascii=False, sort_keys=True))


def main() -> int:
    try:
        validate()
    except AssertionError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print("crop-only Track B provider-failure diagnostic packet validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
