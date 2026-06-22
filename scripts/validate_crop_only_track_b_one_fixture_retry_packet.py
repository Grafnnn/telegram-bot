#!/usr/bin/env python3
"""Validate Track B one-fixture retry packet."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKET_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_track_b_one_fixture_retry_packet_011.md"
MANIFEST_JSON = (
    REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_track_b_one_fixture_retry_packet_011.json"
)
PARENT_DIAGNOSTIC_JSON = (
    REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_provider_failure_diagnostic_010.json"
)
PARENT_HOLD_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_remaining_fixtures_009.json"
FIXTURE_MANIFEST_JSON = (
    REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_visual_quality_expansion_manifest_003.json"
)
EXPECTED_FIXTURE_ID = "pm001-pattern-boundary"

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
    diagnostic = _read_json(PARENT_DIAGNOSTIC_JSON)
    parent_hold = _read_json(PARENT_HOLD_JSON)
    fixture_manifest = _read_json(FIXTURE_MANIFEST_JSON)

    if diagnostic.get("decision") != "READY_FOR_ONE_FIXTURE_RETRY_PACKET_DESIGN":
        raise AssertionError("Parent diagnostic must allow retry packet design.")
    if diagnostic.get("provider_openai_calls") != 0 or diagnostic.get("network_calls") != 0:
        raise AssertionError("Parent diagnostic must be zero-call.")
    if diagnostic.get("failures") != []:
        raise AssertionError("Parent diagnostic must have no failures.")
    if parent_hold.get("decision") != "HOLD_REMAINING_FIXTURES_REVIEW":
        raise AssertionError("Parent remaining-fixtures report must be HOLD.")
    if parent_hold.get("stop_condition") != "provider_call_failed:ImageGenerationProviderError":
        raise AssertionError("Parent remaining-fixtures stop condition mismatch.")

    if manifest.get("manifest_id") != "crop-only-track-b-one-fixture-retry-packet-011":
        raise AssertionError("Unexpected manifest id.")
    if manifest.get("status") != "one_fixture_retry_packet_not_approved_for_execution":
        raise AssertionError("Manifest must remain not approved for execution.")
    if manifest.get("baseline_commit") != "60030731c2c23048ce50ebd80916c89f58ddfcb5":
        raise AssertionError("Baseline mismatch.")
    if manifest.get("experiment_id") != "crop-only-track-b-one-fixture-retry-011":
        raise AssertionError("Unexpected experiment id.")
    if manifest.get("future_target_after_explicit_go") != "local/dev crop-only one-fixture retry":
        raise AssertionError("Unexpected future target.")
    if manifest.get("provider") != "OpenAI":
        raise AssertionError("Provider must be explicit.")
    if manifest.get("provider_model") != "gpt-image-1":
        raise AssertionError("Provider model must be explicit.")
    if manifest.get("endpoint") != "/v1/images/edits":
        raise AssertionError("Endpoint must be explicit.")
    if manifest.get("input_scope") != "crop_source + crop_mask + fabric_reference only":
        raise AssertionError("Input scope must stay crop-only.")
    if manifest.get("fixture_ids_after_go") != [EXPECTED_FIXTURE_ID]:
        raise AssertionError("Retry must be limited to pm001-pattern-boundary.")
    if manifest.get("expected_provider_generations_after_go") != 1:
        raise AssertionError("Expected provider generations must be 1.")
    if manifest.get("max_provider_http_requests_after_go") != 1:
        raise AssertionError("Max provider HTTP requests must be 1.")
    if manifest.get("retry_count_after_go") != 0:
        raise AssertionError("Retry count must be 0.")
    if manifest.get("full_scene_person_input_allowed") is not False:
        raise AssertionError("Full-scene input must be forbidden.")

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

    fixture_by_id = {
        fixture.get("fixture_id"): fixture
        for fixture in fixture_manifest.get("fixtures", [])
        if isinstance(fixture, dict)
    }
    fixture = fixture_by_id.get(EXPECTED_FIXTURE_ID)
    if not isinstance(fixture, dict):
        raise AssertionError("Required fixture missing from fixture manifest.")
    for field in ["crop_source", "crop_mask", "fabric_reference"]:
        reference = fixture.get(field)
        if not isinstance(reference, str):
            raise AssertionError(f"Fixture missing {field}.")
        path = REPO_ROOT / reference
        if not path.is_file():
            raise AssertionError(f"Fixture {field} does not exist: {reference}")

    preservation = manifest.get("preservation_thresholds")
    if not isinstance(preservation, dict):
        raise AssertionError("Missing preservation thresholds.")
    if preservation.get("max_mean_delta") != 1.0:
        raise AssertionError("max_mean_delta must remain 1.0.")
    if preservation.get("max_changed_pixel_percent") != 1.0:
        raise AssertionError("max_changed_pixel_percent must remain 1.0.")
    if preservation.get("pixel_delta_threshold") != 8:
        raise AssertionError("pixel_delta_threshold must remain 8.")

    required_stop_conditions = set(manifest.get("required_stop_conditions", []))
    for condition in [
        "explicit_go_missing",
        "call_cap_would_be_exceeded",
        "retry_would_be_attempted",
        "full_scene_person_input_selected",
        "no_mask_prompt_only_path_selected",
        "secret_base64_raw_payload_exposure_risk",
    ]:
        if condition not in required_stop_conditions:
            raise AssertionError(f"Missing stop condition: {condition}")

    normalized_packet = " ".join(packet.split())
    required_packet_text = [
        "Status: `ONE_FIXTURE_RETRY_PACKET / NOT APPROVED FOR EXECUTION`",
        "Provider/OpenAI calls: `BLOCKED`",
        "Staging/prod/env changes: `BLOCKED`",
        "Runtime/bot/admin behavior changes: `BLOCKED`",
        "User-facing rollout: `BLOCKED`",
        "pm001-pattern-boundary only",
        "Expected provider generations after explicit GO: `1`",
        "Maximum provider HTTP requests after explicit GO: `1`",
        "retry count = 0",
        "Before any execution, request a fresh explicit GO",
    ]
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
    print("crop-only Track B one-fixture retry packet validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
