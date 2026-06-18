from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

from app.services.preservation_service import calculate_outside_mask_drift


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


def test_outside_mask_drift_ignores_editable_clothing_region() -> None:
    base = _synthetic_photo()
    candidate = base.copy()
    ImageDraw.Draw(candidate).rectangle((22, 20, 42, 44), fill=(170, 40, 170), outline=(170, 40, 170))

    drift = calculate_outside_mask_drift(base, candidate, _shirt_mask())

    assert drift.editable_pixel_count == 21 * 25
    assert drift.protected_pixel_count == 64 * 64 - drift.editable_pixel_count
    assert drift.mean_delta == 0
    assert drift.max_delta == 0
    assert drift.changed_pixel_percent == 0
    assert drift.passes(max_mean_delta=1, max_changed_pixel_percent=0)


def test_outside_mask_drift_detects_protected_region_changes() -> None:
    base = _synthetic_photo()
    candidate = base.copy()
    draw = ImageDraw.Draw(candidate)
    draw.rectangle((0, 0, 63, 10), fill=(20, 20, 20))
    draw.ellipse((26, 6, 38, 18), fill=(120, 120, 120), outline=(10, 10, 10))

    drift = calculate_outside_mask_drift(base, candidate, _shirt_mask())

    assert drift.changed_pixel_count > 0
    assert drift.changed_pixel_percent > 1
    assert drift.mean_delta > 1
    assert not drift.passes(max_mean_delta=1, max_changed_pixel_percent=1)


def test_outside_mask_drift_counts_small_tolerated_noise() -> None:
    base = _synthetic_photo()
    candidate = Image.eval(base, lambda value: min(255, value + 2))

    drift = calculate_outside_mask_drift(base, candidate, _shirt_mask(), pixel_delta_threshold=8)

    assert drift.mean_delta == pytest.approx(2)
    assert drift.max_delta == 2
    assert drift.changed_pixel_count == 0
    assert drift.passes(max_mean_delta=3, max_changed_pixel_percent=0)


def test_outside_mask_drift_requires_matching_dimensions() -> None:
    with pytest.raises(ValueError, match="matching dimensions"):
        calculate_outside_mask_drift(
            Image.new("RGB", (64, 64)),
            Image.new("RGB", (32, 32)),
            _shirt_mask(),
        )
