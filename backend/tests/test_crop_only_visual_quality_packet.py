from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_crop_only_visual_quality_packet.py"
PACKET_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_visual_quality_expansion_packet_003.md"
MANIFEST_JSON = (
    REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_visual_quality_expansion_manifest_003.json"
)


def test_crop_only_visual_quality_packet_validator_passes() -> None:
    result = subprocess.run([sys.executable, str(VALIDATOR)], check=False, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr or result.stdout
    assert "crop-only visual quality expansion packet validated" in result.stdout


def test_crop_only_visual_quality_packet_is_not_execution_approval() -> None:
    packet = PACKET_MD.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    assert manifest["status"] == "proposal_only_not_approved_for_execution"
    assert manifest["provider_openai_calls_allowed"] is False
    assert manifest["user_facing_rollout_allowed"] is False
    assert manifest["runtime_enablement_allowed"] is False
    assert manifest["staging_prod_env_allowed"] is False
    assert "Provider/OpenAI calls: `BLOCKED`" in packet
    assert "User-facing rollout: `BLOCKED`" in packet


def test_crop_only_visual_quality_packet_keeps_expansion_fixtures_tbd() -> None:
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    assert manifest["expected_provider_generations"] == 4
    assert manifest["max_total_http_requests"] == 5
    assert [fixture["fixture_id"] for fixture in manifest["fixtures"]] == [
        "pm001-solid-frontal",
        "pm001-pattern-boundary",
        "pm003-large-pattern-scale",
        "pm004-edge-boundary-stress",
    ]
    for fixture in manifest["fixtures"][2:]:
        assert fixture["crop_bounds"] == "TBD"
        assert fixture["expected_crop_dimensions"] == "TBD"
        assert fixture["source_image"].startswith("TBD_SYNTHETIC_")
