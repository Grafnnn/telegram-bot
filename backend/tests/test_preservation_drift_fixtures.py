from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_GENERATOR = REPO_ROOT / "backend" / "tests" / "fixtures" / "preservation_drift" / "create_fixtures.py"
RUNNER = REPO_ROOT / "scripts" / "check_preservation_drift.py"


def _run_case(tmp_path: Path, case: dict[str, object]) -> subprocess.CompletedProcess[str]:
    thresholds = case["thresholds"]
    assert isinstance(thresholds, dict)
    return subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--base",
            str(tmp_path / str(case["base"])),
            "--candidate",
            str(tmp_path / str(case["candidate"])),
            "--mask",
            str(tmp_path / str(case["mask"])),
            "--max-mean-delta",
            str(thresholds["max_mean_delta"]),
            "--max-changed-pixel-percent",
            str(thresholds["max_changed_pixel_percent"]),
            "--pixel-delta-threshold",
            str(thresholds["pixel_delta_threshold"]),
        ],
        check=False,
        text=True,
        capture_output=True,
    )


def test_preservation_drift_fixture_pack_matches_expected_runner_outcomes(tmp_path: Path) -> None:
    generate_result = subprocess.run(
        [sys.executable, str(FIXTURE_GENERATOR), str(tmp_path)],
        check=False,
        text=True,
        capture_output=True,
    )

    assert generate_result.returncode == 0
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    cases = manifest["cases"]
    assert [case["name"] for case in cases] == [
        "clothing_only_pass",
        "protected_region_fail",
        "empty_mask_fail",
        "borderline_threshold_pass",
    ]

    for case in cases:
        result = _run_case(tmp_path, case)
        payload = json.loads(result.stdout)
        assert payload["passes"] is case["expected_pass"]
        assert (result.returncode == 0) is case["expected_pass"]
        assert payload["thresholds"] == case["thresholds"]
