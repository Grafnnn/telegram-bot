#!/usr/bin/env python3
"""Validate Track B remaining-fixtures packet."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKET_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_track_b_remaining_fixtures_packet_009.md"
MANIFEST_JSON = (
    REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_track_b_remaining_fixtures_packet_009.json"
)
PARENT_TRANSPORT_REPORT_JSON = (
    REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_transport_retry_008.json"
)
PARENT_VISUAL_REVIEW_JSON = (
    REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_operator_visual_review_008.json"
)
REQUIRED_FIXTURE_MANIFEST_JSON = (
    REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_visual_quality_expansion_manifest_003.json"
)
EXPECTED_FIXTURE_IDS = [
    "pm001-pattern-boundary",
    "pm003-large-pattern-scale",
    "pm004-edge-boundary-stress",
]
EXCLUDED_FIXTURE_IDS = ["pm001-solid-frontal"]

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
    parent_transport = _read_json(PARENT_TRANSPORT_REPORT_JSON)
    parent_visual = _read_json(PARENT_VISUAL_REVIEW_JSON)
    fixture_manifest = _read_json(REQUIRED_FIXTURE_MANIFEST_JSON)

    if parent_transport.get("decision") != "TRANSPORT_RETRY_READY_FOR_OPERATOR_REVIEW":
        raise AssertionError("Parent transport retry must be ready for operator review.")
    if parent_transport.get("fixture_scope") != EXCLUDED_FIXTURE_IDS:
        raise AssertionError("Parent transport retry must remain the excluded single fixture.")
    if parent_transport.get("actual_provider_http_requests") != 1:
        raise AssertionError("Parent transport retry must record exactly one provider request.")
    if parent_transport.get("retry_count") != 0:
        raise AssertionError("Parent transport retry must have no retry.")

    if parent_visual.get("decision") != "PASS_FOR_MORE_LOCAL_CROP_ONLY_TESTING":
        raise AssertionError("Parent visual review must pass only for more local testing.")
    if parent_visual.get("fixture_id") != EXCLUDED_FIXTURE_IDS[0]:
        raise AssertionError("Parent visual review must be for the excluded fixture.")
    if parent_visual.get("safety", {}).get("user_facing_rollout_approved") is not False:
        raise AssertionError("Parent visual review must not approve rollout.")

    if manifest.get("manifest_id") != "crop-only-track-b-remaining-fixtures-packet-009":
        raise AssertionError("Unexpected manifest id.")
    if manifest.get("status") != "remaining_fixtures_packet_not_approved_for_execution":
        raise AssertionError("Manifest must remain not approved for execution.")
    if manifest.get("baseline_commit") != "d5a77cf0328aee36413c7599a40d92916b61fea6":
        raise AssertionError("Baseline mismatch.")
    if manifest.get("future_target_after_explicit_go") != "local/dev crop-only provider remaining fixtures":
        raise AssertionError("Unexpected future target.")
    if manifest.get("provider") != "OpenAI":
        raise AssertionError("Provider must be explicit.")
    if manifest.get("provider_model") != "gpt-image-1":
        raise AssertionError("Provider model must be explicit.")
    if manifest.get("endpoint") != "/v1/images/edits":
        raise AssertionError("Endpoint must be explicit.")
    if manifest.get("input_scope") != "crop_source + crop_mask + fabric_reference only":
        raise AssertionError("Input scope must stay crop-only.")
    if manifest.get("fixture_ids_after_go") != EXPECTED_FIXTURE_IDS:
        raise AssertionError("Remaining-fixtures scope mismatch.")
    if manifest.get("excluded_fixture_ids") != EXCLUDED_FIXTURE_IDS:
        raise AssertionError("Excluded fixture mismatch.")
    if manifest.get("expected_provider_generations_after_go") != 3:
        raise AssertionError("Expected provider generations must be 3.")
    if manifest.get("max_provider_http_requests_after_go") != 4:
        raise AssertionError("Max provider HTTP requests must be 4.")
    if (
        manifest.get("retry_policy_after_go")
        != "max_1_total_retry_only_for_transient_transport_or_provider_failure_within_four_request_cap"
    ):
        raise AssertionError("Retry policy mismatch.")
    if manifest.get("stop_on_first_threshold_failure_after_go") is not True:
        raise AssertionError("Packet must stop on first threshold failure.")

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
        "full_scene_person_input_allowed",
    ]:
        _assert_false(manifest, key)

    fixture_by_id = {
        fixture.get("fixture_id"): fixture
        for fixture in fixture_manifest.get("fixtures", [])
        if isinstance(fixture, dict)
    }
    for fixture_id in EXPECTED_FIXTURE_IDS:
        fixture = fixture_by_id.get(fixture_id)
        if not isinstance(fixture, dict):
            raise AssertionError(f"Required fixture missing from fixture manifest: {fixture_id}")
        for field in ["crop_source", "crop_mask", "fabric_reference"]:
            reference = fixture.get(field)
            if not isinstance(reference, str):
                raise AssertionError(f"Fixture {fixture_id} missing {field}.")
            path = REPO_ROOT / reference
            if not path.is_file():
                raise AssertionError(f"Fixture {fixture_id} {field} does not exist: {reference}")
    for fixture_id in EXCLUDED_FIXTURE_IDS:
        if fixture_id in manifest.get("fixture_ids_after_go", []):
            raise AssertionError(f"Excluded fixture must not be rerun by this packet: {fixture_id}")

    preservation = manifest.get("preservation_thresholds")
    if not isinstance(preservation, dict):
        raise AssertionError("Missing preservation thresholds.")
    if preservation.get("max_mean_delta") != 1.0:
        raise AssertionError("max_mean_delta must remain 1.0.")
    if preservation.get("max_changed_pixel_percent") != 1.0:
        raise AssertionError("max_changed_pixel_percent must remain 1.0.")
    if preservation.get("pixel_delta_threshold") != 8:
        raise AssertionError("pixel_delta_threshold must remain 8.")

    visual = manifest.get("visual_quality_thresholds")
    if not isinstance(visual, dict):
        raise AssertionError("Missing visual quality thresholds.")
    if visual.get("minimum_average_score") != 4.0:
        raise AssertionError("minimum_average_score must remain 4.0.")
    if visual.get("minimum_dimension_score") != 4:
        raise AssertionError("minimum_dimension_score must remain 4.")
    if visual.get("rollout_approval_from_this_packet") is not False:
        raise AssertionError("Packet must not approve rollout.")

    required_stop_conditions = set(manifest.get("required_stop_conditions", []))
    for condition in [
        "explicit_go_missing",
        "call_cap_would_be_exceeded",
        "retry_would_exceed_cap",
        "full_scene_person_input_selected",
        "no_mask_prompt_only_path_selected",
        "manual_visual_score_below_threshold",
        "secret_base64_raw_payload_exposure_risk",
    ]:
        if condition not in required_stop_conditions:
            raise AssertionError(f"Missing stop condition: {condition}")

    required_packet_text = [
        "Status: `REMAINING_FIXTURES_PACKET / NOT APPROVED FOR EXECUTION`",
        "Provider/OpenAI calls: `BLOCKED`",
        "Staging/prod/env changes: `BLOCKED`",
        "Runtime/bot/admin behavior changes: `BLOCKED`",
        "User-facing rollout: `BLOCKED`",
        "pm001-pattern-boundary",
        "pm003-large-pattern-scale",
        "pm004-edge-boundary-stress",
        "Expected provider generations after explicit GO: `3`",
        "Maximum provider HTTP requests after explicit GO: `4`",
        "Real user photos are forbidden.",
        "Before any execution, request a fresh explicit GO",
    ]
    missing = [phrase for phrase in required_packet_text if phrase not in packet]
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
    print("crop-only Track B remaining-fixtures packet validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
