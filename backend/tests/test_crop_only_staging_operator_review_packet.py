from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_crop_only_staging_operator_review_packet.py"
PACKET_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_staging_operator_review_packet_004.md"
MANIFEST_JSON = (
    REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_staging_operator_review_manifest_004.json"
)


def test_crop_only_staging_operator_review_packet_validator_passes() -> None:
    result = subprocess.run([sys.executable, str(VALIDATOR)], check=False, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr or result.stdout
    assert "crop-only staging operator review packet validated" in result.stdout


def test_crop_only_staging_operator_review_packet_is_not_execution_approval() -> None:
    packet = PACKET_MD.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    assert manifest["status"] == "proposal_only_not_approved_for_execution"
    assert manifest["provider_openai_calls_allowed"] is False
    assert manifest["fake_provider_execution_allowed"] is False
    assert manifest["controlled_provider_execution_allowed"] is False
    assert manifest["user_facing_rollout_allowed"] is False
    assert manifest["runtime_enablement_allowed"] is False
    assert manifest["staging_prod_env_allowed"] is False
    assert manifest["telegram_bot_enablement_allowed"] is False
    assert manifest["admin_user_facing_enablement_allowed"] is False
    assert "Provider/OpenAI calls: `BLOCKED`" in packet
    assert "User-facing rollout: `BLOCKED`" in packet


def test_crop_only_staging_operator_review_packet_tracks_remain_capped() -> None:
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
    tracks = {track["track_id"]: track for track in manifest["tracks"]}

    assert tracks["track_a_fake_provider_staging_route_smoke"]["provider_openai_calls"] == 0
    assert tracks["track_a_fake_provider_staging_route_smoke"]["requires_provider_secrets"] is False
    assert tracks["track_b_controlled_provider_operator_review"]["expected_provider_generations"] == 4
    assert tracks["track_b_controlled_provider_operator_review"]["max_provider_http_requests"] == 5
    assert tracks["track_b_controlled_provider_operator_review"]["requires_provider_secrets"] is True


def test_crop_only_staging_operator_review_reuses_four_synthetic_fixtures() -> None:
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    assert manifest["fixture_ids"] == [
        "pm001-solid-frontal",
        "pm001-pattern-boundary",
        "pm003-large-pattern-scale",
        "pm004-edge-boundary-stress",
    ]
    assert manifest["input_scope"] == "crop_source + crop_mask + fabric_reference only"
    assert manifest["full_scene_person_input_allowed"] is False
    assert manifest["real_user_photos_allowed"] is False
