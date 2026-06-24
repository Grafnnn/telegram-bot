"""Tests for the local user-photo mask preset preflight helper."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "preflight_user_photo_mask_preset.py"
OLD_FIXTURE = REPO_ROOT / "docs" / "experiments" / "assets" / "provider-mask-001" / "pm001-solid-frontal-source.png"


def _run_preflight(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "backend")
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_existing_provider_mask_fixture_fails_visible_inner_tshirt_tiny_coverage() -> None:
    result = _run_preflight(str(OLD_FIXTURE), "--preset", "visible_inner_tshirt")

    assert result.returncode == 1, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["ready"] is False
    assert report["error_code"] == "tiny_coverage"
    assert report["provider_called"] is False
    assert report["coverage_percent"] < report["min_coverage_percent"]


def test_generated_visible_inner_tshirt_fixture_passes_preflight(tmp_path: Path) -> None:
    fixture_path = tmp_path / "visible-inner-tshirt-smoke.png"

    result = _run_preflight(
        "--write-synthetic-visible-inner-tshirt",
        str(fixture_path),
        "--preset",
        "visible_inner_tshirt",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert fixture_path.exists()
    assert report["ready"] is True
    assert report["preset"] == "visible_inner_tshirt"
    assert report["image_size"] == [768, 1024]
    assert report["mask_size"] == [768, 1024]
    assert report["provider_called"] is False
    assert report["min_coverage_percent"] <= report["coverage_percent"] <= report["max_coverage_percent"]
