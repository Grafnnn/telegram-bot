from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_crop_only_track_a_fake_provider_smoke_report.py"
REPORT_JSON = (
    REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_a_fake_provider_smoke_005.json"
)
REPORT_MD = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_a_fake_provider_smoke_005.md"


def test_crop_only_track_a_fake_provider_smoke_report_validator_passes() -> None:
    result = subprocess.run([sys.executable, str(VALIDATOR)], check=False, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr or result.stdout
    assert "crop-only Track A fake-provider smoke report validated" in result.stdout


def test_crop_only_track_a_fake_provider_smoke_report_records_zero_provider_calls() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))

    assert report["decision"] == "TRACK_A_FAKE_PROVIDER_ROUTE_SMOKE_READY"
    assert report["service_level_status"] == "pass"
    assert report["openai_provider_calls"] == 0
    assert report["network_provider_invoked"] is False
    assert report["track_b_controlled_provider_execution"] is False
    assert report["user_facing_rollout_approved"] is False


def test_crop_only_track_a_fake_provider_smoke_report_keeps_route_limitation_explicit() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    report_md = REPORT_MD.read_text(encoding="utf-8")

    assert report["route_level_status"] == (
        "covered_by_ci_pr_75_not_executed_locally_due_missing_fastapi_dependency"
    )
    assert report["local_route_level_attempt"] == {
        "executed": False,
        "reason": "local FastAPI dependency unavailable",
        "route_behavior_covered_by": "PR #75 CI route tests",
    }
    assert "does not claim that staging executed the endpoint" in report_md


def test_crop_only_track_a_fake_provider_smoke_report_uses_four_synthetic_fixtures() -> None:
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))

    assert report["fixture_count"] == 4
    assert report["fixture_ids"] == [
        "pm001-solid-frontal",
        "pm001-pattern-boundary",
        "pm003-large-pattern-scale",
        "pm004-edge-boundary-stress",
    ]
    assert report["real_user_photos_used"] is False
