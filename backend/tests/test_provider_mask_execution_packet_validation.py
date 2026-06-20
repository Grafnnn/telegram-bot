from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKET_PATH = REPO_ROOT / "docs" / "experiments" / "provider_mask_execution_packet_001.md"
MANIFEST_PATH = REPO_ROOT / "docs" / "experiments" / "fixtures" / "provider_mask_fixture_manifest_001.json"
VALIDATOR = REPO_ROOT / "scripts" / "validate_provider_mask_execution_packet.py"


def test_provider_mask_execution_packet_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "validated" in result.stdout


def test_provider_mask_execution_packet_remains_not_approved() -> None:
    packet = PACKET_PATH.read_text(encoding="utf-8")

    assert "Status: DRAFT / NOT APPROVED FOR EXECUTION" in packet
    assert "Execution approval: NOT APPROVED" in packet
    assert "This packet does not authorize provider/OpenAI calls." in packet
    assert "Maximum allowed provider calls: 3" in packet


def test_provider_mask_fixture_manifest_is_synthetic_only() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["real_user_photos_allowed"] is False
    assert manifest["provider_execution_allowed"] is False
    assert manifest["status"] in {
        "draft_not_approved_for_execution",
        "offline_rehearsal_ready_not_approved_for_execution",
    }
    assert [fixture["fixture_id"] for fixture in manifest["fixtures"]] == [
        "pm001-solid-frontal",
        "pm001-pattern-boundary",
    ]
    assert len(manifest["fixtures"]) == 2
    for fixture in manifest["fixtures"]:
        assert fixture["source_image_type"] == "synthetic"
        assert fixture["allowed_target"] == "local/dev future execution only"
        assert "background" in fixture["protected_regions"]
