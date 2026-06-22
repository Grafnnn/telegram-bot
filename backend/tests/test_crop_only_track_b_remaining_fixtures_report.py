from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_crop_only_track_b_remaining_fixtures_report.py"
REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_remaining_fixtures_009.json"
REPORT_MD = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_remaining_fixtures_009.md"


def test_crop_only_track_b_remaining_fixtures_report_validator_passes() -> None:
    result = subprocess.run([sys.executable, str(VALIDATOR)], check=False, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr or result.stdout
    assert "crop-only Track B remaining-fixtures report validated" in result.stdout


def test_crop_only_track_b_remaining_fixtures_report_records_hold() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))

    assert report["decision"] == "HOLD_REMAINING_FIXTURES_REVIEW"
    assert report["stop_condition"] == "provider_call_failed:ImageGenerationProviderError"
    assert report["fixtures"] == []
    assert report["actual_provider_http_requests"] == 2
    assert report["retry_count"] == 1


def test_crop_only_track_b_remaining_fixtures_report_preserves_scope_and_caps() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))

    assert report["fixture_scope"] == [
        "pm001-pattern-boundary",
        "pm003-large-pattern-scale",
        "pm004-edge-boundary-stress",
    ]
    assert report["excluded_fixture_ids"] == ["pm001-solid-frontal"]
    assert report["expected_provider_generations"] == 3
    assert report["max_provider_http_requests"] == 4
    assert report["full_scene_provider_input_used"] is False


def test_crop_only_track_b_remaining_fixtures_report_does_not_approve_rollout() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    report_md = REPORT_MD.read_text(encoding="utf-8")

    assert report["provider_outputs_committed"] is False
    assert report["raw_provider_payloads_committed"] is False
    assert report["staging_prod_env_touched"] is False
    assert report["runtime_bot_admin_user_facing_enabled"] is False
    assert report["real_user_photos_used"] is False
    assert report["user_facing_rollout_approved"] is False
    assert "A future attempt needs a new issue comment/packet" in " ".join(report_md.split())
