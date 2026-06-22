from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_crop_only_track_b_operator_visual_review.py"
REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_operator_visual_review_008.json"
REPORT_MD = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_operator_visual_review_008.md"


def test_crop_only_track_b_operator_visual_review_validator_passes() -> None:
    result = subprocess.run([sys.executable, str(VALIDATOR)], check=False, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr or result.stdout
    assert "crop-only Track B operator visual review validated" in result.stdout


def test_crop_only_track_b_operator_visual_review_records_local_testing_pass() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))

    assert report["decision"] == "PASS_FOR_MORE_LOCAL_CROP_ONLY_TESTING"
    assert report["fixture_id"] == "pm001-solid-frontal"
    assert report["manual_operator_review_completed"] is True
    assert report["provider_output_binary_committed"] is False


def test_crop_only_track_b_operator_visual_review_scores_remain_conservative() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    scores = report["scores"]

    assert scores["overall_average"] == 4.2
    assert scores["garment_only_localization"] == 5
    assert min(value for key, value in scores.items() if key != "overall_average") >= 4


def test_crop_only_track_b_operator_visual_review_does_not_approve_rollout() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    report_md = REPORT_MD.read_text(encoding="utf-8")

    assert report["safety"]["user_facing_rollout_approved"] is False
    assert report["safety"]["new_provider_calls"] is False
    assert report["safety"]["staging_prod_env_touched"] is False
    assert report["safety"]["runtime_bot_admin_user_facing_enabled"] is False
    assert "does not approve broader fixture execution" in report_md
