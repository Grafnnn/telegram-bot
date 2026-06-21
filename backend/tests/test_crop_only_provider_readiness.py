from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_crop_only_provider_readiness.py"
READINESS_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_provider_readiness_001.md"
FROZEN_INPUTS_JSON = (
    REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_provider_frozen_inputs_001.json"
)
PACKET_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_provider_execution_packet_001.md"


def test_crop_only_provider_readiness_validator_passes() -> None:
    result = subprocess.run([sys.executable, str(VALIDATOR)], check=False, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr or result.stdout
    assert "crop-only provider readiness validated" in result.stdout


def test_crop_only_provider_readiness_manifest_freezes_two_synthetic_fixtures() -> None:
    manifest = json.loads(FROZEN_INPUTS_JSON.read_text(encoding="utf-8"))

    assert manifest["manifest_id"] == "crop-only-provider-frozen-inputs-001"
    assert manifest["issue_gate"] == 64
    assert manifest["provider_openai_calls_allowed"] is False
    assert manifest["user_facing_rollout_allowed"] is False
    assert manifest["runtime_enablement_allowed"] is False
    assert manifest["expected_provider_calls"] == 2
    assert manifest["max_provider_calls"] == 3
    assert [fixture["fixture_id"] for fixture in manifest["fixtures"]] == [
        "pm001-solid-frontal",
        "pm001-pattern-boundary",
    ]
    for fixture in manifest["fixtures"]:
        assert fixture["expected_provider_input"] == "crop_source + crop_mask + fabric_reference only"
        assert fixture["notes"] == "Synthetic fixture only. No real user photo."


def test_crop_only_provider_readiness_docs_remain_not_approved() -> None:
    readiness = READINESS_MD.read_text(encoding="utf-8")
    packet = PACKET_MD.read_text(encoding="utf-8")

    assert "Status: READYNESS REVIEW ONLY / NOT APPROVED FOR EXECUTION" in readiness
    assert "Execution approval: NOT APPROVED" in readiness
    assert "Provider/OpenAI calls: BLOCKED" in readiness
    assert "User-facing rollout: NOT APPROVED" in readiness
    assert "Runtime enablement: NOT APPROVED" in readiness
    assert "Issue #64 is the approval gate, but this document does not itself approve execution." in readiness
    assert "crop_only_provider_readiness_001.md" in packet
    assert "crop_only_provider_frozen_inputs_001.json" in packet
