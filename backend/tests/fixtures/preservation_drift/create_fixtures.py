#!/usr/bin/env python3
"""Create deterministic synthetic fixtures for preservation drift experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw


FIXTURE_SIZE = (64, 64)


def _synthetic_photo() -> Image.Image:
    image = Image.new("RGB", FIXTURE_SIZE, (240, 240, 240))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 48, 63, 63), fill=(220, 220, 220))
    draw.ellipse((26, 6, 38, 18), fill=(215, 180, 150), outline=(40, 40, 40))
    draw.rectangle((22, 20, 42, 44), fill=(40, 80, 170), outline=(30, 30, 30))
    draw.rectangle((14, 22, 21, 42), fill=(215, 180, 150), outline=(40, 40, 40))
    draw.rectangle((43, 22, 50, 42), fill=(215, 180, 150), outline=(40, 40, 40))
    return image


def _shirt_mask() -> Image.Image:
    mask = Image.new("RGBA", FIXTURE_SIZE, (0, 0, 0, 255))
    draw = ImageDraw.Draw(mask)
    draw.rectangle((22, 20, 42, 44), fill=(0, 0, 0, 0))
    return mask


def _opaque_mask() -> Image.Image:
    return Image.new("RGBA", FIXTURE_SIZE, (0, 0, 0, 255))


def _clothing_edit(base: Image.Image) -> Image.Image:
    candidate = base.copy()
    ImageDraw.Draw(candidate).rectangle((22, 20, 42, 44), fill=(170, 40, 170), outline=(170, 40, 170))
    return candidate


def _protected_region_edit(base: Image.Image) -> Image.Image:
    candidate = base.copy()
    draw = ImageDraw.Draw(candidate)
    draw.rectangle((0, 0, 63, 10), fill=(20, 20, 20))
    draw.ellipse((26, 6, 38, 18), fill=(120, 120, 120), outline=(10, 10, 10))
    return candidate


def _borderline_noise(base: Image.Image) -> Image.Image:
    return ImageChops.add(base, Image.new("RGB", FIXTURE_SIZE, (1, 1, 1)))


def _case_payload(
    *,
    name: str,
    expected_pass: bool,
    max_mean_delta: float = 1.0,
    max_changed_pixel_percent: float = 1.0,
    pixel_delta_threshold: int = 8,
    notes: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "base": f"{name}/base.png",
        "candidate": f"{name}/candidate.png",
        "mask": f"{name}/mask.png",
        "expected_pass": expected_pass,
        "thresholds": {
            "max_mean_delta": max_mean_delta,
            "max_changed_pixel_percent": max_changed_pixel_percent,
            "pixel_delta_threshold": pixel_delta_threshold,
        },
        "notes": notes,
    }


def _write_case(output_dir: Path, name: str, base: Image.Image, candidate: Image.Image, mask: Image.Image) -> None:
    case_dir = output_dir / name
    case_dir.mkdir(parents=True, exist_ok=True)
    base.save(case_dir / "base.png")
    candidate.save(case_dir / "candidate.png")
    mask.save(case_dir / "mask.png")


def create_fixtures(output_dir: Path) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    base = _synthetic_photo()

    cases = [
        _case_payload(
            name="clothing_only_pass",
            expected_pass=True,
            notes="Only transparent clothing-mask pixels change.",
        ),
        _case_payload(
            name="protected_region_fail",
            expected_pass=False,
            notes="Protected face/background pixels change outside the editable mask.",
        ),
        _case_payload(
            name="empty_mask_fail",
            expected_pass=False,
            notes="The mask has no transparent editable region, so a clothing change is protected drift.",
        ),
        _case_payload(
            name="borderline_threshold_pass",
            expected_pass=True,
            max_mean_delta=1.0,
            max_changed_pixel_percent=0.0,
            notes="Every protected pixel changes by exactly one RGB level, matching the mean threshold.",
        ),
    ]

    _write_case(output_dir, "clothing_only_pass", base, _clothing_edit(base), _shirt_mask())
    _write_case(output_dir, "protected_region_fail", base, _protected_region_edit(base), _shirt_mask())
    _write_case(output_dir, "empty_mask_fail", base, _clothing_edit(base), _opaque_mask())
    _write_case(output_dir, "borderline_threshold_pass", base, _borderline_noise(base), _shirt_mask())

    (output_dir / "manifest.json").write_text(json.dumps({"cases": cases}, indent=2, sort_keys=True) + "\n")
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Create synthetic preservation drift fixture images and manifest.")
    parser.add_argument("output_dir", type=Path, help="Directory where fixture images and manifest.json will be written.")
    args = parser.parse_args()

    cases = create_fixtures(args.output_dir)
    print(f"Wrote {len(cases)} preservation drift fixture cases to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
