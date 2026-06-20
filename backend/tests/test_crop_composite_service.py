from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

from app.services.crop_composite_service import (
    CropBox,
    composite_edited_crop,
    find_editable_crop_box,
    prepare_crop_inputs,
)
from app.services.preservation_service import calculate_outside_mask_drift


def _source_image() -> Image.Image:
    image = Image.new("RGB", (80, 80), color=(240, 240, 240))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 60, 79, 79), fill=(220, 220, 220))
    draw.ellipse((34, 8, 46, 20), fill=(214, 178, 145), outline=(30, 30, 30))
    draw.rectangle((26, 24, 54, 54), fill=(50, 90, 170), outline=(20, 20, 20))
    draw.rectangle((16, 28, 25, 52), fill=(214, 178, 145), outline=(30, 30, 30))
    draw.rectangle((55, 28, 64, 52), fill=(214, 178, 145), outline=(30, 30, 30))
    return image


def _shirt_mask() -> Image.Image:
    mask = Image.new("RGBA", (80, 80), color=(0, 0, 0, 255))
    ImageDraw.Draw(mask).rectangle((26, 24, 54, 54), fill=(0, 0, 0, 0))
    return mask


def test_find_editable_crop_box_returns_transparent_region_bounds() -> None:
    crop_box = find_editable_crop_box(_shirt_mask())

    assert crop_box == CropBox(left=26, top=24, right=55, bottom=55)
    assert crop_box.width == 29
    assert crop_box.height == 31


def test_find_editable_crop_box_expands_and_clamps_padding() -> None:
    crop_box = find_editable_crop_box(_shirt_mask(), padding_pixels=40)

    assert crop_box == CropBox(left=0, top=0, right=80, bottom=80)


def test_find_editable_crop_box_rejects_empty_mask() -> None:
    mask = Image.new("RGBA", (80, 80), color=(0, 0, 0, 255))

    with pytest.raises(ValueError, match="no editable pixels"):
        find_editable_crop_box(mask)


def test_prepare_crop_inputs_returns_aligned_source_and_mask_crops() -> None:
    crop_inputs = prepare_crop_inputs(_source_image(), _shirt_mask(), padding_pixels=4)

    assert crop_inputs.crop_box == CropBox(left=22, top=20, right=59, bottom=59)
    assert crop_inputs.source_crop.size == (37, 39)
    assert crop_inputs.mask_crop.size == crop_inputs.source_crop.size
    assert crop_inputs.mask_crop.mode == "RGBA"
    assert crop_inputs.mask_crop.getchannel("A").getextrema()[0] == 0


def test_prepare_crop_inputs_requires_matching_source_and_mask_size() -> None:
    source = _source_image()
    mask = Image.new("RGBA", (40, 40), color=(0, 0, 0, 255))

    with pytest.raises(ValueError, match="dimensions must match"):
        prepare_crop_inputs(source, mask)


def test_composite_edited_crop_changes_only_editable_mask_pixels() -> None:
    source = _source_image()
    mask = _shirt_mask()
    crop_inputs = prepare_crop_inputs(source, mask, padding_pixels=6)
    edited_crop = Image.new("RGB", crop_inputs.source_crop.size, color=(190, 40, 150))

    result = composite_edited_crop(source, edited_crop, mask, crop_inputs.crop_box)
    drift = calculate_outside_mask_drift(source, result, mask)

    assert drift.mean_delta == 0
    assert drift.changed_pixel_count == 0
    assert drift.changed_pixel_percent == 0
    assert result.getpixel((30, 30)) == (190, 40, 150)
    assert result.getpixel((20, 30)) == source.getpixel((20, 30))
    assert result.getpixel((40, 12)) == source.getpixel((40, 12))


def test_composite_edited_crop_requires_matching_crop_size() -> None:
    source = _source_image()
    mask = _shirt_mask()
    crop_inputs = prepare_crop_inputs(source, mask)
    edited_crop = Image.new("RGB", (crop_inputs.crop_box.width + 1, crop_inputs.crop_box.height), color=(0, 0, 0))

    with pytest.raises(ValueError, match="Edited crop dimensions"):
        composite_edited_crop(source, edited_crop, mask, crop_inputs.crop_box)


def test_composite_edited_crop_rejects_out_of_bounds_crop_box() -> None:
    source = _source_image()
    mask = _shirt_mask()
    edited_crop = Image.new("RGB", (10, 10), color=(0, 0, 0))

    with pytest.raises(ValueError, match="inside source image bounds"):
        composite_edited_crop(source, edited_crop, mask, CropBox(left=-1, top=0, right=9, bottom=10))
