#!/usr/bin/env python3
"""Validate crop-only staging operator review packet proposal."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKET_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_staging_operator_review_packet_004.md"
MANIFEST_JSON = (
    REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_staging_operator_review_manifest_004.json"
)
PARENT_REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_visual_quality_expansion_003.json"
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
    parent_report = _read_json(PARENT_REPORT_JSON)
    required_fixture_manifest = _read_json(REQUIRED_FIXTURE_MANIFEST_JSON)

    if parent_report.get("decision") != "GO_FOR_MORE_CROP_ONLY_TESTING":
        raise AssertionError("Parent visual-quality evidence must allow only more crop-only testing.")
    if parent_report.get("user_facing_rollout_approved") is not False:
        raise AssertionError("Parent visual-quality evidence must not approve rollout.")
    if parent_report.get("successful_provider_generations") != 4:
        raise AssertionError("Parent evidence must include four successful provider generations.")
    if parent_report.get("total_http_requests") != 5:
        raise AssertionError("Parent evidence must preserve the five-request cap history.")

    if manifest.get("manifest_id") != "crop-only-staging-operator-review-004":
        raise AssertionError("Unexpected manifest id.")
    if manifest.get("status") != "proposal_only_not_approved_for_execution":
        raise AssertionError("Manifest must remain proposal-only.")
    for key in [
        "provider_openai_calls_allowed",
        "fake_provider_execution_allowed",
        "controlled_provider_execution_allowed",
        "user_facing_rollout_allowed",
        "runtime_enablement_allowed",
        "staging_prod_env_allowed",
        "telegram_bot_enablement_allowed",
        "admin_user_facing_enablement_allowed",
        "real_user_photos_allowed",
        "imports_sql_direct_db_writes_allowed",
        "full_scene_person_input_allowed",
    ]:
        _assert_false(manifest, key)

    if manifest.get("parent_decision_required") != "GO_FOR_MORE_CROP_ONLY_TESTING":
        raise AssertionError("Parent decision requirement mismatch.")
    if manifest.get("input_scope") != "crop_source + crop_mask + fabric_reference only":
        raise AssertionError("Input scope must stay crop-only.")
    if manifest.get("fixture_ids") != EXPECTED_FIXTURE_IDS:
        raise AssertionError("Unexpected fixture ids or order.")

    required_fixture_ids = [fixture.get("fixture_id") for fixture in required_fixture_manifest.get("fixtures", [])]
    if required_fixture_ids != EXPECTED_FIXTURE_IDS:
        raise AssertionError("Required fixture manifest must still contain the expected four fixtures.")

    tracks = manifest.get("tracks")
    if not isinstance(tracks, list) or len(tracks) != 2:
        raise AssertionError("Manifest must define exactly two proposed tracks.")
    track_a, track_b = tracks
    if track_a.get("track_id") != "track_a_fake_provider_staging_route_smoke":
        raise AssertionError("Track A id mismatch.")
    if track_a.get("provider_openai_calls") != 0:
        raise AssertionError("Track A must require zero provider/OpenAI calls.")
    if track_a.get("requires_provider_secrets") is not False:
        raise AssertionError("Track A must not require provider secrets.")
    if track_b.get("track_id") != "track_b_controlled_provider_operator_review":
        raise AssertionError("Track B id mismatch.")
    if track_b.get("expected_provider_generations") != 4:
        raise AssertionError("Track B expected generations must be 4.")
    if track_b.get("max_provider_http_requests") != 5:
        raise AssertionError("Track B provider HTTP request cap must be 5.")
    if track_b.get("requires_provider_secrets") is not True:
        raise AssertionError("Track B must explicitly require provider secret availability.")

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

    required_packet_text = [
        "Status: `PROPOSAL_ONLY / NOT APPROVED FOR EXECUTION`",
        "Provider/OpenAI calls: `BLOCKED`",
        "Staging/prod/env changes: `BLOCKED`",
        "Runtime/bot/admin behavior changes: `BLOCKED`",
        "User-facing rollout: `BLOCKED`",
        "Provider/OpenAI calls: `0`",
        "Expected provider generations: `4`",
        "Maximum provider HTTP requests: `5`",
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
    print("crop-only staging operator review packet validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
