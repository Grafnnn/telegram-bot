from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_crop_only_track_b_provider_failure_diagnostic_packet.py"
PACKET_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_track_b_provider_failure_diagnostic_packet_010.md"
MANIFEST_JSON = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "fixtures"
    / "crop_only_track_b_provider_failure_diagnostic_packet_010.json"
)


def test_crop_only_track_b_provider_failure_diagnostic_packet_validator_passes() -> None:
    result = subprocess.run([sys.executable, str(VALIDATOR)], check=False, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr or result.stdout
    assert "crop-only Track B provider-failure diagnostic packet validated" in result.stdout


def test_crop_only_track_b_provider_failure_diagnostic_packet_blocks_provider_execution() -> None:
    packet = PACKET_MD.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    assert manifest["status"] == "provider_failure_diagnostic_packet_not_approved_for_provider_execution"
    assert manifest["provider_openai_calls_allowed"] is False
    assert manifest["controlled_provider_execution_allowed"] is False
    assert manifest["diagnostic_provider_calls_allowed"] is False
    assert manifest["diagnostic_network_calls_allowed"] is False
    assert "Provider/OpenAI calls: `BLOCKED`" in packet


def test_crop_only_track_b_provider_failure_diagnostic_packet_requires_zero_call_checks_first() -> None:
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    checks = set(manifest["required_zero_call_checks"])
    assert "fixture_paths_exist" in checks
    assert "crop_mask_has_editable_transparent_region" in checks
    assert "crop_source_and_mask_dimensions_match" in checks
    assert "sanitized_request_shape_built" in checks
    assert "full_scene_provider_input_absent" in checks


def test_crop_only_track_b_provider_failure_diagnostic_packet_limits_future_retry_candidate() -> None:
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
    retry = manifest["future_retry_candidate_after_separate_go"]

    assert retry["fixture_ids"] == ["pm001-pattern-boundary"]
    assert retry["expected_provider_generations"] == 1
    assert retry["max_provider_http_requests"] == 1
    assert retry["retry_count"] == 0
    assert retry["input_scope"] == "crop_source + crop_mask + fabric_reference only"
    assert retry["full_scene_person_input_allowed"] is False
    assert manifest["user_facing_rollout_allowed"] is False
