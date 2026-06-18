from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_preservation_drift.py"


def _synthetic_photo() -> Image.Image:
    image = Image.new("RGB", (64, 64), (240, 240, 240))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 48, 63, 63), fill=(220, 220, 220))
    draw.ellipse((26, 6, 38, 18), fill=(215, 180, 150), outline=(40, 40, 40))
    draw.rectangle((22, 20, 42, 44), fill=(40, 80, 170), outline=(30, 30, 30))
    draw.rectangle((14, 22, 21, 42), fill=(215, 180, 150), outline=(40, 40, 40))
    draw.rectangle((43, 22, 50, 42), fill=(215, 180, 150), outline=(40, 40, 40))
    return image


def _shirt_mask() -> Image.Image:
    mask = Image.new("RGBA", (64, 64), (0, 0, 0, 255))
    draw = ImageDraw.Draw(mask)
    draw.rectangle((22, 20, 42, 44), fill=(0, 0, 0, 0))
    return mask


def _write_fixture_triplet(tmp_path: Path, candidate: Image.Image) -> tuple[Path, Path, Path]:
    base_path = tmp_path / "base.png"
    candidate_path = tmp_path / "candidate.png"
    mask_path = tmp_path / "mask.png"
    _synthetic_photo().save(base_path)
    candidate.save(candidate_path)
    _shirt_mask().save(mask_path)
    return base_path, candidate_path, mask_path


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        text=True,
        capture_output=True,
    )


def test_preservation_drift_script_passes_when_only_clothing_region_changes(tmp_path: Path) -> None:
    candidate = _synthetic_photo()
    ImageDraw.Draw(candidate).rectangle((22, 20, 42, 44), fill=(170, 40, 170), outline=(170, 40, 170))
    base_path, candidate_path, mask_path = _write_fixture_triplet(tmp_path, candidate)

    result = _run_script(
        "--base",
        str(base_path),
        "--candidate",
        str(candidate_path),
        "--mask",
        str(mask_path),
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["passes"] is True
    assert payload["drift"]["mean_delta"] == 0
    assert payload["drift"]["changed_pixel_percent"] == 0


def test_preservation_drift_script_fails_when_protected_region_changes(tmp_path: Path) -> None:
    candidate = _synthetic_photo()
    draw = ImageDraw.Draw(candidate)
    draw.rectangle((0, 0, 63, 10), fill=(20, 20, 20))
    draw.ellipse((26, 6, 38, 18), fill=(120, 120, 120), outline=(10, 10, 10))
    base_path, candidate_path, mask_path = _write_fixture_triplet(tmp_path, candidate)

    result = _run_script(
        "--base",
        str(base_path),
        "--candidate",
        str(candidate_path),
        "--mask",
        str(mask_path),
        "--max-mean-delta",
        "1",
        "--max-changed-pixel-percent",
        "1",
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["passes"] is False
    assert payload["drift"]["mean_delta"] > 1
    assert payload["drift"]["changed_pixel_percent"] > 1


def test_preservation_drift_script_can_write_json_report(tmp_path: Path) -> None:
    base_path, candidate_path, mask_path = _write_fixture_triplet(tmp_path, _synthetic_photo())
    output_path = tmp_path / "report.json"

    result = _run_script(
        "--base",
        str(base_path),
        "--candidate",
        str(candidate_path),
        "--mask",
        str(mask_path),
        "--output",
        str(output_path),
        "--pretty",
    )

    assert result.returncode == 0
    assert output_path.is_file()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["passes"] is True
    assert payload["thresholds"]["max_mean_delta"] == 1.0
