from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_GENERATOR = REPO_ROOT / "backend" / "tests" / "fixtures" / "preservation_drift" / "create_fixtures.py"
EXPERIMENT_RUNNER = REPO_ROOT / "scripts" / "run_preservation_drift_experiments.py"


def test_preservation_drift_experiment_runner_collects_reports_and_summary(tmp_path: Path) -> None:
    fixtures_root = tmp_path / "fixtures"
    reports_root = tmp_path / "reports"
    summary_path = reports_root / "summary.json"
    markdown_summary_path = reports_root / "summary.md"

    fixture_result = subprocess.run(
        [sys.executable, str(FIXTURE_GENERATOR), str(fixtures_root)],
        check=False,
        text=True,
        capture_output=True,
    )
    assert fixture_result.returncode == 0, fixture_result.stderr or fixture_result.stdout

    result = subprocess.run(
        [
            sys.executable,
            str(EXPERIMENT_RUNNER),
            "--manifest",
            str(fixtures_root / "manifest.json"),
            "--fixtures-root",
            str(fixtures_root),
            "--output-dir",
            str(reports_root),
            "--summary",
            str(summary_path),
            "--markdown-summary",
            str(markdown_summary_path),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert summary_path.is_file()
    assert markdown_summary_path.is_file()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["total_cases"] == 4
    assert summary["passed_count"] == 2
    assert summary["failed_count"] == 2
    assert summary["expected_match_count"] == 4
    assert summary["unexpected_result_count"] == 0
    assert summary["all_expected"] is True

    expected_by_name = {
        "clothing_only_pass": True,
        "protected_region_fail": False,
        "empty_mask_fail": False,
        "borderline_threshold_pass": True,
    }
    assert [case["name"] for case in summary["cases"]] == list(expected_by_name)

    for case in summary["cases"]:
        assert case["expected_pass"] is expected_by_name[case["name"]]
        assert case["actual_pass"] is expected_by_name[case["name"]]
        assert case["expected_matches_actual"] is True
        assert Path(case["report_path"]).is_file()
        assert set(case["thresholds"]) == {
            "max_mean_delta",
            "max_changed_pixel_percent",
            "pixel_delta_threshold",
        }
        assert set(case["drift"]) >= {
            "mean_delta",
            "changed_pixel_percent",
            "max_delta",
            "protected_pixel_count",
            "editable_pixel_count",
        }

    markdown = markdown_summary_path.read_text(encoding="utf-8")
    assert "| case | expected | actual | match |" in markdown
    assert "clothing_only_pass" in markdown
