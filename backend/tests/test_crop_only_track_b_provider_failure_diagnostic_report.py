from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_crop_only_track_b_provider_failure_diagnostic_report.py"
REPORT_JSON = (
    REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_provider_failure_diagnostic_010.json"
)
REPORT_MD = (
    REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_provider_failure_diagnostic_010.md"
)


def test_crop_only_track_b_provider_failure_diagnostic_report_validator_passes() -> None:
    result = subprocess.run([sys.executable, str(VALIDATOR)], check=False, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr or result.stdout
    assert "crop-only Track B provider-failure diagnostic report validated" in result.stdout


def test_crop_only_track_b_provider_failure_diagnostic_report_is_zero_call() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))

    assert report["decision"] == "READY_FOR_ONE_FIXTURE_RETRY_PACKET_DESIGN"
    assert report["provider_openai_calls"] == 0
    assert report["network_calls"] == 0
    assert report["diagnostic_provider_calls_allowed"] is False
    assert report["diagnostic_network_calls_allowed"] is False
    assert report["failures"] == []


def test_crop_only_track_b_provider_failure_diagnostic_report_validates_fixtures() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))

    assert [fixture["fixture_id"] for fixture in report["fixtures"]] == [
        "pm001-pattern-boundary",
        "pm003-large-pattern-scale",
        "pm004-edge-boundary-stress",
    ]
    for fixture in report["fixtures"]:
        assert fixture["crop_source_mask_dimensions_match"] is True
        assert fixture["crop_mask"]["has_alpha"] is True
        assert fixture["crop_mask"]["has_editable_region"] is True
        assert fixture["crop_mask"]["has_protected_region"] is True
        assert fixture["fabric_reference"]["non_empty"] is True


def test_crop_only_track_b_provider_failure_diagnostic_report_does_not_approve_retry_or_rollout() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    report_md = REPORT_MD.read_text(encoding="utf-8")

    assert report["future_retry_candidate"]["fixture_ids"] == ["pm001-pattern-boundary"]
    assert report["future_retry_candidate"]["max_provider_http_requests"] == 1
    assert report["future_retry_candidate"]["retry_count"] == 0
    assert report["safety"]["user_facing_rollout_approved"] is False
    assert "This report does not authorize provider/OpenAI execution." in report_md
