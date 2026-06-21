from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_crop_only_retry_packet.py"
PACKET_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_provider_retry_packet_002.md"
MANIFEST_JSON = REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_provider_retry_manifest_002.json"


def test_crop_only_retry_packet_validator_passes() -> None:
    result = subprocess.run([sys.executable, str(VALIDATOR)], check=False, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr or result.stdout
    assert "crop-only retry packet validated" in result.stdout


def test_crop_only_retry_packet_remains_not_approved() -> None:
    packet = PACKET_MD.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    assert manifest["status"] == "retry_packet_proposal_only"
    assert manifest["issue_gate"] == 66
    assert manifest["provider_openai_calls_allowed"] is False
    assert manifest["user_facing_rollout_allowed"] is False
    assert manifest["runtime_enablement_allowed"] is False
    assert manifest["expected_provider_calls"] == 2
    assert manifest["max_provider_calls"] == 3
    assert "Execution approval: NOT APPROVED" in packet
    assert "Provider/OpenAI calls: BLOCKED" in packet


def test_crop_only_retry_packet_requires_explicit_reconciliation() -> None:
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    assert manifest["dimension_strategy"]["name"] == "center_crop_to_crop_aspect_then_resize"
    assert manifest["dimension_strategy"]["implicit_resize_allowed"] is False
    assert manifest["dimension_strategy"]["reconciliation_required_before_composite"] is True
    for fixture in manifest["fixtures"]:
        assert fixture["expected_provider_input"] == "crop_source + crop_mask + fabric_reference only"
        assert fixture["expected_reconciliation"] == (
            "center-crop provider output to crop aspect, then resize to expected crop dimensions"
        )
