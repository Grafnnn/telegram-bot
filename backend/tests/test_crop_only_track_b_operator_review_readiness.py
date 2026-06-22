from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_crop_only_track_b_operator_review_readiness.py"
PACKET_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_track_b_operator_review_readiness_006.md"
MANIFEST_JSON = (
    REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_track_b_operator_review_readiness_006.json"
)


def test_crop_only_track_b_operator_review_readiness_validator_passes() -> None:
    result = subprocess.run([sys.executable, str(VALIDATOR)], check=False, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr or result.stdout
    assert "crop-only Track B operator review readiness packet validated" in result.stdout


def test_crop_only_track_b_operator_review_readiness_is_not_execution_approval() -> None:
    packet = PACKET_MD.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    assert manifest["status"] == "readiness_packet_not_approved_for_execution"
    assert manifest["provider_openai_calls_allowed"] is False
    assert manifest["controlled_provider_execution_allowed"] is False
    assert manifest["staging_prod_env_allowed"] is False
    assert manifest["runtime_enablement_allowed"] is False
    assert manifest["user_facing_rollout_allowed"] is False
    assert "Provider/OpenAI calls: `BLOCKED`" in packet
    assert "User-facing rollout: `BLOCKED`" in packet


def test_crop_only_track_b_operator_review_readiness_caps_future_provider_calls() -> None:
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    assert manifest["provider"] == "OpenAI"
    assert manifest["provider_model"] == "gpt-image-1"
    assert manifest["endpoint"] == "/v1/images/edits"
    assert manifest["expected_provider_generations_after_go"] == 4
    assert manifest["max_provider_http_requests_after_go"] == 5
    assert manifest["retry_policy_after_go"] == (
        "max_1_total_retry_only_for_transient_provider_failure_within_http_cap"
    )


def test_crop_only_track_b_operator_review_readiness_stays_crop_only() -> None:
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    assert manifest["input_scope"] == "crop_source + crop_mask + fabric_reference only"
    assert manifest["full_scene_person_input_allowed"] is False
    assert manifest["fixture_ids"] == [
        "pm001-solid-frontal",
        "pm001-pattern-boundary",
        "pm003-large-pattern-scale",
        "pm004-edge-boundary-stress",
    ]
    assert manifest["real_user_photos_allowed"] is False
