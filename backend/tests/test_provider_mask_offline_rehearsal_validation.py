from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "scripts" / "generate_provider_mask_offline_rehearsal.py"
VALIDATOR = REPO_ROOT / "scripts" / "validate_provider_mask_offline_rehearsal.py"
PACKET_PATH = REPO_ROOT / "docs" / "experiments" / "provider_mask_execution_packet_001.md"
MANIFEST_PATH = REPO_ROOT / "docs" / "experiments" / "fixtures" / "provider_mask_fixture_manifest_001.json"
PRESERVATION_REPORT = (
    REPO_ROOT / "docs" / "experiments" / "reports" / "provider_mask_preservation_rehearsal_001.json"
)
VISUAL_REPORT = (
    REPO_ROOT / "docs" / "experiments" / "reports" / "provider_mask_visual_quality_rehearsal_001.md"
)


def test_provider_mask_offline_rehearsal_validation_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "validated" in result.stdout


def test_provider_mask_rehearsal_generator_is_offline_documented() -> None:
    text = GENERATOR.read_text(encoding="utf-8")

    assert "does not call OpenAI/provider" in text
    assert "does not use real user photos" in text
    assert "Image.new" in text


def test_provider_mask_rehearsal_manifest_references_existing_synthetic_pngs() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["status"] == "offline_rehearsal_ready_not_approved_for_execution"
    assert manifest["real_user_photos_allowed"] is False
    assert manifest["provider_execution_allowed"] is False
    assert len(manifest["fixtures"]) == 2

    for fixture in manifest["fixtures"]:
        assert fixture["source_image_type"] == "synthetic"
        for field in ["source_image_reference", "mask_reference", "fabric_reference", "fake_output_reference"]:
            path = REPO_ROOT / fixture[field]
            assert path.is_file(), fixture[field]
            with Image.open(path) as image:
                assert image.format == "PNG"


def test_provider_mask_rehearsal_reports_remain_non_execution_artifacts() -> None:
    packet = PACKET_PATH.read_text(encoding="utf-8")
    preservation = json.loads(PRESERVATION_REPORT.read_text(encoding="utf-8"))
    visual = VISUAL_REPORT.read_text(encoding="utf-8")

    assert "Status: DRAFT / NOT APPROVED FOR EXECUTION" in packet
    assert "Execution approval: NOT APPROVED" in packet
    assert preservation["provider_openai_called"] is False
    assert preservation["experiment_executed"] is False
    assert all(entry["pass_fail"] == "pass" for entry in preservation["entries"])
    assert "OFFLINE REHEARSAL ONLY / NOT PROVIDER EXECUTION" in visual
