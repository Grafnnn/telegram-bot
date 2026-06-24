from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image, ImageDraw

from app.services.preservation_service import (
    PreservationThresholds,
    calculate_outside_mask_drift,
    evaluate_generated_image_preservation,
)


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


def _polygon_shirt_mask() -> Image.Image:
    mask = Image.new("RGBA", (64, 64), (0, 0, 0, 255))
    draw = ImageDraw.Draw(mask)
    draw.polygon([(24, 20), (40, 20), (45, 32), (41, 46), (23, 46), (19, 32)], fill=(0, 0, 0, 0))
    return mask


def _png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


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


def test_generated_image_preservation_passes_when_only_editable_region_changes(tmp_path) -> None:
    base = _synthetic_photo()
    mask = _shirt_mask()
    candidate = base.copy()
    ImageDraw.Draw(candidate).rectangle((22, 20, 42, 44), fill=(160, 30, 180), outline=(160, 30, 180))
    base_path = tmp_path / "base.png"
    mask_path = tmp_path / "mask.png"
    base.save(base_path, format="PNG")
    mask.save(mask_path, format="PNG")

    result = evaluate_generated_image_preservation(
        source_image_path=base_path,
        candidate_image_bytes=_png_bytes(candidate),
        mask_image_path=mask_path,
        thresholds=PreservationThresholds(max_mean_delta=0, max_changed_pixel_percent=0, pixel_delta_threshold=8),
    )

    assert result.passes is True
    assert result.reason is None
    assert result.drift is not None
    assert result.drift.mean_delta == 0
    assert result.drift.changed_pixel_percent == 0


def test_generated_image_preservation_fails_rectangular_overlay_inside_mask_bounds(tmp_path) -> None:
    base = _synthetic_photo()
    mask = _polygon_shirt_mask()
    candidate = base.copy()
    ImageDraw.Draw(candidate).rectangle((19, 20, 45, 46), fill=(20, 180, 40))
    base_path = tmp_path / "base.png"
    mask_path = tmp_path / "mask.png"
    base.save(base_path, format="PNG")
    mask.save(mask_path, format="PNG")

    result = evaluate_generated_image_preservation(
        source_image_path=base_path,
        candidate_image_bytes=_png_bytes(candidate),
        mask_image_path=mask_path,
        thresholds=PreservationThresholds(max_mean_delta=1, max_changed_pixel_percent=1, pixel_delta_threshold=8),
    )

    assert result.passes is False
    assert result.reason == "rectangular_overlay_detected"


def test_generated_image_preservation_allows_polygon_mask_shaped_edit(tmp_path) -> None:
    base = _synthetic_photo()
    mask = _polygon_shirt_mask()
    candidate = base.copy().convert("RGB")
    alpha = mask.getchannel("A")
    pixels = candidate.load()
    for y in range(candidate.height):
        for x in range(candidate.width):
            if alpha.getpixel((x, y)) < 128:
                pixels[x, y] = (20, 180, 40)
    base_path = tmp_path / "base.png"
    mask_path = tmp_path / "mask.png"
    base.save(base_path, format="PNG")
    mask.save(mask_path, format="PNG")

    result = evaluate_generated_image_preservation(
        source_image_path=base_path,
        candidate_image_bytes=_png_bytes(candidate),
        mask_image_path=mask_path,
        thresholds=PreservationThresholds(max_mean_delta=1, max_changed_pixel_percent=1, pixel_delta_threshold=8),
    )

    assert result.passes is True
    assert result.reason is None


def test_generated_image_preservation_fails_when_protected_region_changes(tmp_path) -> None:
    base = _synthetic_photo()
    mask = _shirt_mask()
    candidate = base.copy()
    ImageDraw.Draw(candidate).rectangle((0, 0, 63, 12), fill=(15, 15, 15))
    base_path = tmp_path / "base.png"
    mask_path = tmp_path / "mask.png"
    base.save(base_path, format="PNG")
    mask.save(mask_path, format="PNG")

    result = evaluate_generated_image_preservation(
        source_image_path=base_path,
        candidate_image_bytes=_png_bytes(candidate),
        mask_image_path=mask_path,
        thresholds=PreservationThresholds(max_mean_delta=1, max_changed_pixel_percent=1, pixel_delta_threshold=8),
    )

    assert result.passes is False
    assert result.reason == "protected_region_drift"
    assert result.drift is not None
    assert result.drift.mean_delta > 1
    assert result.drift.changed_pixel_percent > 1


def test_generated_image_preservation_fails_size_mismatch(tmp_path) -> None:
    base_path = tmp_path / "base.png"
    mask_path = tmp_path / "mask.png"
    _synthetic_photo().save(base_path, format="PNG")
    _shirt_mask().save(mask_path, format="PNG")

    result = evaluate_generated_image_preservation(
        source_image_path=base_path,
        candidate_image_bytes=_png_bytes(Image.new("RGB", (32, 32), color=(255, 0, 0))),
        mask_image_path=mask_path,
    )

    assert result.passes is False
    assert result.reason == "size_mismatch"
    assert result.drift is None


def test_generated_image_preservation_fails_empty_editable_region(tmp_path) -> None:
    base = _synthetic_photo()
    mask = Image.new("RGBA", (64, 64), (0, 0, 0, 255))
    base_path = tmp_path / "base.png"
    mask_path = tmp_path / "mask.png"
    base.save(base_path, format="PNG")
    mask.save(mask_path, format="PNG")

    result = evaluate_generated_image_preservation(
        source_image_path=base_path,
        candidate_image_bytes=_png_bytes(base),
        mask_image_path=mask_path,
    )

    assert result.passes is False
    assert result.reason == "empty_editable_mask_region"


def test_generated_image_preservation_threshold_equality_passes(tmp_path) -> None:
    base = _synthetic_photo()
    mask = _shirt_mask()
    candidate = Image.eval(base, lambda value: min(255, value + 1))
    base_path = tmp_path / "base.png"
    mask_path = tmp_path / "mask.png"
    base.save(base_path, format="PNG")
    mask.save(mask_path, format="PNG")

    result = evaluate_generated_image_preservation(
        source_image_path=base_path,
        candidate_image_bytes=_png_bytes(candidate),
        mask_image_path=mask_path,
        thresholds=PreservationThresholds(max_mean_delta=1, max_changed_pixel_percent=0, pixel_delta_threshold=8),
    )

    assert result.passes is True
    assert result.drift is not None
    assert result.drift.mean_delta == pytest.approx(1)
    assert result.drift.changed_pixel_percent == 0
