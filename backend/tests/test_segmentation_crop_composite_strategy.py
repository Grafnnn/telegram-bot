from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STRATEGY_PATH = REPO_ROOT / "docs" / "segmentation_crop_composite_strategy.md"
VALIDATOR = REPO_ROOT / "scripts" / "validate_segmentation_crop_composite_strategy.py"


def test_segmentation_crop_composite_strategy_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "validated" in result.stdout


def test_segmentation_crop_composite_strategy_is_design_only() -> None:
    text = STRATEGY_PATH.read_text(encoding="utf-8")
    normalized = " ".join(text.lower().split())

    assert "Status: DESIGN GATE / NOT APPROVED FOR EXECUTION" in text
    assert "This document does not authorize provider/OpenAI calls" in text
    assert "do not run provider calls until that rehearsal passes" in normalized
    assert "provider-mask-001" in text
    assert "NO-GO" in text


def test_segmentation_crop_composite_strategy_requires_fail_closed_composite() -> None:
    text = STRATEGY_PATH.read_text(encoding="utf-8")

    assert "Provider output must never bypass the composite and preservation steps." in text
    assert "provider output is never used as the final full image directly" in text
    assert "failed preservation output has no successful `result_image_url`" in text
