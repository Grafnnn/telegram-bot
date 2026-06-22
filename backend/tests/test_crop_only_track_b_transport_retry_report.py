from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_crop_only_track_b_transport_retry_report.py"
REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_transport_retry_008.json"
REPORT_MD = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_transport_retry_008.md"


def test_crop_only_track_b_transport_retry_report_validator_passes() -> None:
    result = subprocess.run([sys.executable, str(VALIDATOR)], check=False, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr or result.stdout
    assert "crop-only Track B transport retry report validated" in result.stdout


def test_crop_only_track_b_transport_retry_report_records_successful_transport() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))

    assert report["decision"] == "TRANSPORT_RETRY_READY_FOR_OPERATOR_REVIEW"
    assert report["actual_provider_http_requests"] == 1
    assert report["retry_count"] == 0
    assert report["stop_condition"] is None
    assert report["fixture_scope"] == ["pm001-solid-frontal"]


def test_crop_only_track_b_transport_retry_report_preserves_safety_boundaries() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))

    assert report["input_scope"] == "crop_source + crop_mask + fabric_reference only"
    assert report["full_scene_provider_input_used"] is False
    assert report["staging_prod_env_touched"] is False
    assert report["runtime_bot_admin_user_facing_enabled"] is False
    assert report["imports_sql_direct_db_writes"] is False
    assert report["real_user_photos_used"] is False
    assert report["raw_provider_payloads_committed"] is False
    assert report["provider_outputs_committed"] is False
    assert report["user_facing_rollout_approved"] is False


def test_crop_only_track_b_transport_retry_report_records_preservation_pass() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    fixture = report["fixtures"][0]
    report_md = REPORT_MD.read_text(encoding="utf-8")

    assert fixture["fixture_id"] == "pm001-solid-frontal"
    assert fixture["preservation"] == "pass"
    assert fixture["provider_output_dimensions"] == {"width": 1024, "height": 1536}
    assert fixture["reconciled_crop_dimensions"] == {"width": 57, "height": 105}
    assert fixture["mean_delta_protected_region"] == 0.0
    assert fixture["changed_pixel_percent_protected_region"] == 0.0
    assert fixture["max_delta_protected_region"] == 0
    assert "does not approve user-facing Telegram/admin behavior" in report_md
