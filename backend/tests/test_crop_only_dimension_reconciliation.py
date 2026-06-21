from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = REPO_ROOT / "scripts" / "run_crop_only_dimension_reconciliation_rehearsal.py"
VALIDATOR = REPO_ROOT / "scripts" / "validate_crop_only_dimension_reconciliation.py"
REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_dimension_reconciliation_001.json"


def test_crop_only_dimension_reconciliation_runner_and_validator_pass() -> None:
    runner = subprocess.run([sys.executable, str(RUNNER)], check=False, text=True, capture_output=True)
    assert runner.returncode == 0, runner.stderr or runner.stdout

    validator = subprocess.run([sys.executable, str(VALIDATOR)], check=False, text=True, capture_output=True)
    assert validator.returncode == 0, validator.stderr or validator.stdout
    assert "crop-only dimension reconciliation validated" in validator.stdout


def test_crop_only_dimension_reconciliation_remains_offline_only() -> None:
    payload = json.loads(REPORT_JSON.read_text(encoding="utf-8"))

    assert payload["status"] == "offline_rehearsal_passed"
    assert payload["strategy"] == "center_crop_to_crop_aspect_then_resize"
    assert payload["provider_openai_called"] is False
    assert payload["provider_retry_authorized"] is False
    assert payload["runtime_behavior_changed"] is False
    assert payload["user_facing_rollout_approved"] is False
    assert payload["decision"] == "READY_FOR_RETRY_PACKET_DESIGN_ONLY"


def test_crop_only_dimension_reconciliation_matches_crop_dimensions() -> None:
    payload = json.loads(REPORT_JSON.read_text(encoding="utf-8"))

    for fixture in payload["fixtures"]:
        assert fixture["pass_fail"] == "pass"
        assert fixture["protected_region_drift"] is False
        assert fixture["oversized_provider_output_dimensions"] == {"width": 1024, "height": 1536}
        assert fixture["reconciled_crop_dimensions"] == fixture["crop_source_dimensions"]
