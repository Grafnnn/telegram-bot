from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_crop_only_visual_quality_report.py"
REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_visual_quality_expansion_003.json"
REPORT_MD = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_visual_quality_expansion_003.md"


def test_crop_only_visual_quality_report_validator_passes() -> None:
    result = subprocess.run([sys.executable, str(VALIDATOR)], check=False, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr or result.stdout
    assert "crop-only visual quality expansion 003 report validated" in result.stdout


def test_crop_only_visual_quality_report_keeps_rollout_blocked() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    markdown = REPORT_MD.read_text(encoding="utf-8")

    assert report["decision"] == "GO_FOR_MORE_CROP_ONLY_TESTING"
    assert report["successful_provider_generations"] == 4
    assert report["total_http_requests"] == 5
    assert report["retry_count"] == 1
    assert report["user_facing_rollout_approved"] is False
    assert report["staging_prod_env_touched"] is False
    assert "It does not approve production rollout" in markdown


def test_crop_only_visual_quality_report_records_all_fixture_passes() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))

    assert [fixture["fixture_id"] for fixture in report["fixtures"]] == [
        "pm001-solid-frontal",
        "pm001-pattern-boundary",
        "pm003-large-pattern-scale",
        "pm004-edge-boundary-stress",
    ]
    for fixture in report["fixtures"]:
        assert fixture["preservation"] == "pass"
        assert fixture["visual_review"] == "pass"
        assert fixture["mean_delta_protected_region"] == 0.0
        assert fixture["changed_pixel_percent_protected_region"] == 0.0
        assert fixture["minimum_visual_dimension_score"] >= 4
