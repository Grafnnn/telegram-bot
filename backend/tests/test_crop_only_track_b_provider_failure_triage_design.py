from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_crop_only_track_b_provider_failure_triage_design.py"
DESIGN_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_track_b_provider_failure_triage_design_012.md"
MANIFEST_JSON = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "fixtures"
    / "crop_only_track_b_provider_failure_triage_design_012.json"
)


def test_crop_only_track_b_provider_failure_triage_design_validator_passes() -> None:
    result = subprocess.run([sys.executable, str(VALIDATOR)], check=False, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr or result.stdout
    assert "crop-only Track B provider-failure triage design validated" in result.stdout


def test_crop_only_track_b_provider_failure_triage_design_blocks_provider_execution() -> None:
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
    design = DESIGN_MD.read_text(encoding="utf-8")

    assert manifest["status"] == "provider_failure_triage_design_not_approved_for_provider_execution"
    assert manifest["provider_openai_calls_allowed"] is False
    assert manifest["controlled_provider_execution_allowed"] is False
    assert manifest["future_provider_retry_allowed"] is False
    assert manifest["same_shape_provider_retry_allowed"] is False
    assert "Provider/OpenAI calls: `BLOCKED`" in design


def test_crop_only_track_b_provider_failure_triage_design_records_repeated_failure() -> None:
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    evidence = manifest["parent_evidence"]
    assert [entry["decision"] for entry in evidence] == [
        "HOLD_REMAINING_FIXTURES_REVIEW",
        "READY_FOR_ONE_FIXTURE_RETRY_PACKET_DESIGN",
        "HOLD_ONE_FIXTURE_RETRY",
    ]
    assert evidence[0]["stop_condition"] == "provider_call_failed:ImageGenerationProviderError"
    assert evidence[2]["stop_condition"] == "provider_call_failed:ImageGenerationProviderError"
    assert evidence[1]["provider_openai_calls"] == 0
    assert "Repeated provider failure" in manifest["repeated_failure_conclusion"]


def test_crop_only_track_b_provider_failure_triage_design_requires_zero_call_matrix_next() -> None:
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    next_gate = manifest["next_gate"]
    assert next_gate["type"] == "zero_call_request_shape_compatibility_matrix"
    assert next_gate["call_count"] == 0
    assert next_gate["provider_calls_allowed"] is False
    assert "fresh_go_required_before_execution" in next_gate["required_fields"]
    assert all(
        variant["provider_calls_now"] == 0
        for variant in manifest["request_shape_variants_to_compare_zero_call"]
    )
