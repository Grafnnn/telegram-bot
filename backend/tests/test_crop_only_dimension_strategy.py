from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_crop_only_dimension_strategy.py"
REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_provider_execution_001.json"
STRATEGY_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_output_dimension_strategy_001.md"


def test_crop_only_dimension_strategy_validator_passes() -> None:
    result = subprocess.run([sys.executable, str(VALIDATOR)], check=False, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr or result.stdout
    assert "crop-only dimension strategy validated" in result.stdout


def test_crop_only_execution_report_records_hold_without_rollout() -> None:
    payload = json.loads(REPORT_JSON.read_text(encoding="utf-8"))

    assert payload["decision"] == "HOLD_PROVIDER_OUTPUT_SIZE_MISMATCH"
    assert payload["actual_provider_calls"] == 1
    assert payload["expected_provider_calls"] == 2
    assert payload["max_provider_calls"] == 3
    assert payload["stopped_before_second_fixture"] is True
    assert payload["user_facing_rollout_approved"] is False
    assert payload["provider_output_images_committed"] is False
    assert payload["raw_provider_payloads_committed"] is False


def test_crop_only_dimension_strategy_is_not_retry_approval() -> None:
    strategy = STRATEGY_MD.read_text(encoding="utf-8")

    assert "Status: STRATEGY GATE / NOT APPROVED FOR RETRY" in strategy
    assert "It does not approve another provider/OpenAI call." in strategy
    assert "Do not run another provider call yet." in strategy
    assert "This strategy document does not approve:" in strategy
