from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_crop_only_provider_packet.py"
PACKET_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_provider_execution_packet_001.md"
MANIFEST_JSON = REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_provider_fixture_manifest_001.json"


def test_crop_only_provider_packet_validator_passes() -> None:
    result = subprocess.run([sys.executable, str(VALIDATOR)], check=False, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr or result.stdout
    assert "crop-only provider packet validated" in result.stdout


def test_crop_only_provider_packet_is_not_execution_approval() -> None:
    packet = PACKET_MD.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    assert manifest["status"] == "packet_proposal_only"
    assert manifest["execution_approved"] is False
    assert manifest["provider_calls_authorized"] is False
    assert manifest["provider_openai_called"] is False
    assert manifest["runtime_behavior_changed"] is False
    assert manifest["user_facing_rollout_approved"] is False
    assert "This packet does not authorize provider/OpenAI calls." in packet
    assert "Execution allowed now: `no`" in packet


def test_crop_only_provider_packet_forbids_full_scene_provider_inputs() -> None:
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    assert manifest["call_cap"]["expected_provider_calls"] == 2
    assert manifest["call_cap"]["max_allowed_provider_calls"] == 3
    for fixture in manifest["fixtures"]:
        assert fixture["expected_provider_input"] == "crop_source_plus_crop_mask_plus_fabric_image"
        assert fixture["full_scene_provider_input_allowed"] is False
        assert fixture["crop_source"].startswith("docs/experiments/assets/crop-composite-001/")
        assert fixture["crop_mask"].startswith("docs/experiments/assets/crop-composite-001/")
