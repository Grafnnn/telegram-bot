from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = REPO_ROOT / "scripts" / "run_crop_composite_offline_rehearsal.py"
VALIDATOR = REPO_ROOT / "scripts" / "validate_crop_composite_offline_rehearsal.py"
REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_composite_offline_rehearsal_001.json"
REPORT_MD = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_composite_offline_rehearsal_001.md"


def test_crop_composite_offline_rehearsal_runner_and_validator_pass() -> None:
    runner = subprocess.run([sys.executable, str(RUNNER)], check=False, text=True, capture_output=True)
    assert runner.returncode == 0, runner.stderr or runner.stdout

    validator = subprocess.run([sys.executable, str(VALIDATOR)], check=False, text=True, capture_output=True)
    assert validator.returncode == 0, validator.stderr or validator.stdout
    assert "validated" in validator.stdout


def test_crop_composite_offline_rehearsal_report_is_design_only() -> None:
    payload = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    markdown = REPORT_MD.read_text(encoding="utf-8")

    assert payload["status"] == "offline_rehearsal_passed"
    assert payload["provider_openai_called"] is False
    assert payload["experiment_executed"] is False
    assert payload["runtime_behavior_changed"] is False
    assert payload["provider_calls_authorized"] is False
    assert payload["user_facing_rollout_approved"] is False
    assert payload["decision"] == "READY_FOR_CAPPED_PROVIDER_PACKET_DESIGN_ONLY"
    assert "It does not call OpenAI/provider." in markdown
    assert "It does not approve future provider calls." in markdown


def test_crop_composite_offline_rehearsal_preserves_protected_regions() -> None:
    payload = json.loads(REPORT_JSON.read_text(encoding="utf-8"))

    assert [entry["fixture_id"] for entry in payload["fixtures"]] == [
        "pm001-solid-frontal",
        "pm001-pattern-boundary",
    ]
    for entry in payload["fixtures"]:
        assert entry["pass_fail"] == "pass"
        assert entry["protected_region_drift"] is False
        assert entry["mean_delta_protected_region"] == 0
        assert entry["changed_pixel_percent_protected_region"] == 0
        assert entry["max_delta_protected_region"] == 0
