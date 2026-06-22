#!/usr/bin/env python3
"""Validate Track B operator-review readiness packet."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKET_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_track_b_operator_review_readiness_006.md"
MANIFEST_JSON = (
    REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_track_b_operator_review_readiness_006.json"
)
TRACK_A_REPORT_JSON = (
    REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_a_fake_provider_smoke_005.json"
)
REQUIRED_FIXTURE_MANIFEST_JSON = (
    REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_visual_quality_expansion_manifest_003.json"
)
EXPECTED_FIXTURE_IDS = [
    "pm001-solid-frontal",
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
    track_a_report = _read_json(TRACK_A_REPORT_JSON)
    required_fixture_manifest = _read_json(REQUIRED_FIXTURE_MANIFEST_JSON)

    if track_a_report.get("decision") != "TRACK_A_FAKE_PROVIDER_ROUTE_SMOKE_READY":
        raise AssertionError("Track A report must be ready before Track B readiness.")
    if track_a_report.get("openai_provider_calls") != 0:
        raise AssertionError("Track A report must preserve zero provider/OpenAI calls.")
    if track_a_report.get("user_facing_rollout_approved") is not False:
        raise AssertionError("Track A report must not approve rollout.")

    if manifest.get("manifest_id") != "crop-only-track-b-operator-review-readiness-006":
        raise AssertionError("Unexpected manifest id.")
    if manifest.get("status") != "readiness_packet_not_approved_for_execution":
        raise AssertionError("Manifest must remain not approved for execution.")
    if manifest.get("baseline_commit") != "787665fb05e19eb78ec25105f80a093c267ab91d":
        raise AssertionError("Baseline mismatch.")
    if manifest.get("parent_track_a_decision_required") != "TRACK_A_FAKE_PROVIDER_ROUTE_SMOKE_READY":
        raise AssertionError("Parent Track A decision requirement mismatch.")
    if manifest.get("future_target_after_explicit_go") != "local/dev controlled provider operator review":
        raise AssertionError("Unexpected future target.")
    if manifest.get("provider") != "OpenAI":
        raise AssertionError("Provider must be explicit.")
    if manifest.get("provider_model") != "gpt-image-1":
        raise AssertionError("Provider model must be explicit.")
    if manifest.get("endpoint") != "/v1/images/edits":
        raise AssertionError("Endpoint must be explicit.")
    if manifest.get("input_scope") != "crop_source + crop_mask + fabric_reference only":
        raise AssertionError("Input scope must remain crop-only.")
    if manifest.get("expected_provider_generations_after_go") != 4:
        raise AssertionError("Expected provider generation count must be 4.")
    if manifest.get("max_provider_http_requests_after_go") != 5:
        raise AssertionError("Max provider HTTP request cap must be 5.")
    if manifest.get("retry_policy_after_go") != "max_1_total_retry_only_for_transient_provider_failure_within_http_cap":
        raise AssertionError("Retry policy mismatch.")
    if manifest.get("fixture_ids") != EXPECTED_FIXTURE_IDS:
        raise AssertionError("Unexpected fixture ids or order.")

    for key in [
        "provider_openai_calls_allowed",
        "controlled_provider_execution_allowed",
        "staging_prod_env_allowed",
        "runtime_enablement_allowed",
        "telegram_bot_enablement_allowed",
        "admin_user_facing_enablement_allowed",
        "user_facing_rollout_allowed",
        "real_user_photos_allowed",
        "imports_sql_direct_db_writes_allowed",
        "full_scene_person_input_allowed",
    ]:
        _assert_false(manifest, key)

    required_fixture_ids = [fixture.get("fixture_id") for fixture in required_fixture_manifest.get("fixtures", [])]
    if required_fixture_ids != EXPECTED_FIXTURE_IDS:
        raise AssertionError("Required fixture manifest must still contain the expected four fixtures.")

    preservation = manifest.get("preservation_thresholds")
    if not isinstance(preservation, dict):
        raise AssertionError("Missing preservation thresholds.")
    if preservation.get("max_mean_delta") != 1.0:
        raise AssertionError("max_mean_delta must remain 1.0.")
    if preservation.get("max_changed_pixel_percent") != 1.0:
        raise AssertionError("max_changed_pixel_percent must remain 1.0.")
    if preservation.get("pixel_delta_threshold") != 8:
        raise AssertionError("pixel_delta_threshold must remain 8.")

    review = manifest.get("visual_operator_review_thresholds")
    if not isinstance(review, dict):
        raise AssertionError("Missing visual/operator review thresholds.")
    if review.get("minimum_average_score") != 4.0:
        raise AssertionError("Visual average threshold must be 4.0.")
    if review.get("minimum_dimension_score") != 4:
        raise AssertionError("Minimum dimension score must be 4.")
    if review.get("operator_review_required") is not True:
        raise AssertionError("Operator review must be required.")
    if review.get("rollout_approval_from_this_packet") is not False:
        raise AssertionError("This packet must not approve rollout.")

    required_stop_conditions = set(manifest.get("required_stop_conditions", []))
    for condition in [
        "explicit_go_missing",
        "call_cap_would_be_exceeded",
        "full_scene_person_input_selected",
        "no_mask_prompt_only_path_selected",
        "preservation_report_missing_or_failing",
        "visual_operator_review_missing_or_failing",
        "secret_base64_raw_payload_exposure_risk",
    ]:
        if condition not in required_stop_conditions:
            raise AssertionError(f"Missing stop condition: {condition}")

    required_packet_text = [
        "Status: `READINESS_PACKET / NOT APPROVED FOR EXECUTION`",
        "Provider/OpenAI calls: `BLOCKED`",
        "Staging/prod/env changes: `BLOCKED`",
        "Runtime/bot/admin behavior changes: `BLOCKED`",
        "User-facing rollout: `BLOCKED`",
        "Expected provider generations after explicit GO: `4`",
        "Maximum provider HTTP requests after explicit GO: `5`",
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
    print("crop-only Track B operator review readiness packet validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
