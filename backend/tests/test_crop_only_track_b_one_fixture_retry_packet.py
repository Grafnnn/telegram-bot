from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_crop_only_track_b_one_fixture_retry_packet.py"
PACKET_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_track_b_one_fixture_retry_packet_011.md"
MANIFEST_JSON = (
    REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_track_b_one_fixture_retry_packet_011.json"
)


def test_crop_only_track_b_one_fixture_retry_packet_validator_passes() -> None:
    result = subprocess.run([sys.executable, str(VALIDATOR)], check=False, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr or result.stdout
    assert "crop-only Track B one-fixture retry packet validated" in result.stdout


def test_crop_only_track_b_one_fixture_retry_packet_is_not_execution_approval() -> None:
    packet = PACKET_MD.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    assert manifest["status"] == "one_fixture_retry_packet_not_approved_for_execution"
    assert manifest["provider_openai_calls_allowed"] is False
    assert manifest["controlled_provider_execution_allowed"] is False
    assert manifest["staging_prod_env_allowed"] is False
    assert manifest["runtime_enablement_allowed"] is False
    assert manifest["user_facing_rollout_allowed"] is False
    assert "Provider/OpenAI calls: `BLOCKED`" in packet


def test_crop_only_track_b_one_fixture_retry_packet_is_one_request_zero_retry() -> None:
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    assert manifest["fixture_ids_after_go"] == ["pm001-pattern-boundary"]
    assert manifest["expected_provider_generations_after_go"] == 1
    assert manifest["max_provider_http_requests_after_go"] == 1
    assert manifest["retry_count_after_go"] == 0
    assert manifest["excluded_fixture_ids"] == [
        "pm001-solid-frontal",
        "pm003-large-pattern-scale",
        "pm004-edge-boundary-stress",
    ]


def test_crop_only_track_b_one_fixture_retry_packet_stays_crop_only_and_non_rollout() -> None:
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    assert manifest["input_scope"] == "crop_source + crop_mask + fabric_reference only"
    assert manifest["full_scene_person_input_allowed"] is False
    assert manifest["real_user_photos_allowed"] is False
    assert manifest["visual_quality_approval_allowed"] is False
    assert manifest["user_facing_rollout_allowed"] is False
