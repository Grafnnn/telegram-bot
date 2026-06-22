from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_crop_only_track_b_operator_review_report.py"
REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_operator_review_006.json"
REPORT_MD = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_operator_review_006.md"


def test_crop_only_track_b_operator_review_report_validator_passes() -> None:
    result = subprocess.run([sys.executable, str(VALIDATOR)], check=False, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr or result.stdout
    assert "crop-only Track B operator review report validated" in result.stdout


def test_crop_only_track_b_operator_review_report_records_hold() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))

    assert report["decision"] == "HOLD_TRACK_B_OPERATOR_REVIEW"
    assert report["stop_condition"] == "provider_call_failed:URLError"
    assert report["actual_provider_http_requests"] == 2
    assert report["retry_count"] == 1
    assert report["fixtures"] == []


def test_crop_only_track_b_operator_review_report_preserves_safety_boundaries() -> None:
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


def test_crop_only_track_b_operator_review_report_requires_fresh_go_for_retry() -> None:
    report_md = REPORT_MD.read_text(encoding="utf-8")

    assert "Any retry or new Track B execution requires a fresh explicit GO packet." in report_md
    assert "does not approve" in report_md
