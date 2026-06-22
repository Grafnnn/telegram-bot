from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_crop_only_provider_retry_report.py"
REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_provider_retry_002.json"
REPORT_MD = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_provider_retry_002.md"


def test_crop_only_provider_retry_report_validator_passes() -> None:
    result = subprocess.run([sys.executable, str(VALIDATOR)], check=False, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr or result.stdout
    assert "crop-only provider retry 002 report validated" in result.stdout


def test_crop_only_provider_retry_report_preserves_safety_boundaries() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    markdown = REPORT_MD.read_text(encoding="utf-8")

    assert report["decision"] == "GO_FOR_MORE_CROP_ONLY_TESTING"
    assert report["actual_provider_generations"] == 2
    assert report["full_scene_provider_input_used"] is False
    assert report["real_user_photos_used"] is False
    assert report["staging_prod_env_touched"] is False
    assert report["runtime_bot_behavior_changed"] is False
    assert report["imports_sql_direct_db_writes"] is False
    assert report["user_facing_rollout_approved"] is False
    assert "It does not approve production rollout" in markdown


def test_crop_only_provider_retry_report_records_zero_protected_drift() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))

    assert [entry["fixture_id"] for entry in report["fixtures"]] == [
        "pm001-solid-frontal",
        "pm001-pattern-boundary",
    ]
    for entry in report["fixtures"]:
        assert entry["preservation"] == "pass"
        assert entry["mean_delta_protected_region"] == 0.0
        assert entry["changed_pixel_percent_protected_region"] == 0.0
        assert entry["max_delta_protected_region"] == 0
        assert entry["dimension_action"] == "center_crop_to_crop_aspect_then_resize"
