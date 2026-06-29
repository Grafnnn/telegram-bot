"""Tests for deterministic local texture-transfer try-on service."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw

from app.services.local_texture_transfer_service import (
    LOCAL_TEXTURE_TRANSFER_VERSION,
    LocalTextureTransferError,
    transfer_fabric_texture_locally,
)


def _write_source(path: Path) -> None:
    image = Image.new("RGB", (160, 200), color=(32, 38, 46))
    draw = ImageDraw.Draw(image)
    draw.ellipse((66, 14, 94, 42), fill=(190, 145, 118))
    draw.rectangle((54, 72, 106, 170), fill=(222, 220, 210))
    for offset, shade in ((0, 188), (13, 220), (26, 244), (39, 205)):
        draw.rectangle((54 + offset, 72, 66 + offset, 170), fill=(shade, shade, shade))
    draw.rectangle((30, 62, 58, 172), fill=(25, 120, 72))
    draw.rectangle((102, 62, 130, 172), fill=(25, 120, 72))
    image.save(path, format="PNG")


def _write_fabric(path: Path) -> None:
    image = Image.new("RGB", (80, 80), color=(120, 45, 160))
    draw = ImageDraw.Draw(image)
    for x in range(0, 80, 8):
        draw.line((x, 0, x, 79), fill=(230, 210, 80), width=2)
    for y in range(0, 80, 12):
        draw.line((0, y, 79, y), fill=(70, 25, 110), width=2)
    image.save(path, format="PNG")


def _write_mask(path: Path, *, box: tuple[int, int, int, int] = (54, 72, 106, 170)) -> None:
    mask = Image.new("RGBA", (160, 200), color=(0, 0, 0, 255))
    draw = ImageDraw.Draw(mask)
    draw.polygon(
        [
            (box[0] + 4, box[1]),
            (box[2] - 4, box[1]),
            (box[2], box[1] + 34),
            (box[2] - 8, box[3]),
            (box[0] + 8, box[3]),
            (box[0], box[1] + 34),
        ],
        fill=(0, 0, 0, 0),
    )
    mask.save(path, format="PNG")


def _paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "source.png"
    fabric = tmp_path / "fabric.png"
    mask = tmp_path / "mask.png"
    _write_source(source)
    _write_fabric(fabric)
    _write_mask(mask)
    return source, fabric, mask


def test_local_texture_transfer_changes_only_masked_region_and_preserves_size(tmp_path: Path) -> None:
    source, fabric, mask = _paths(tmp_path)

    result = transfer_fabric_texture_locally(
        original_image_path=source,
        fabric_reference_path=fabric,
        mask_image_path=mask,
        min_coverage_percent=1.0,
        max_coverage_percent=80.0,
        feather_radius=3,
    )

    output_path = tmp_path / "output.png"
    output_path.write_bytes(result.image_bytes)
    with Image.open(source) as original, Image.open(output_path) as output, Image.open(mask) as mask_image:
        assert output.size == original.size
        alpha = mask_image.convert("RGBA").getchannel("A")
        diff = ImageChops.difference(original.convert("RGB"), output.convert("RGB"))
        diff_pixels = diff.load()
        alpha_pixels = alpha.load()
        outside_changed = 0
        inside_changed = 0
        for y in range(output.height):
            for x in range(output.width):
                if max(diff_pixels[x, y]) > 0:
                    if alpha_pixels[x, y] < 128:
                        inside_changed += 1
                    else:
                        outside_changed += 1

    assert inside_changed > 0
    assert outside_changed == 0
    assert result.metadata.local_transfer_version == LOCAL_TEXTURE_TRANSFER_VERSION
    assert result.metadata.provider_called is False
    assert result.metadata.outside_mask_mean_delta == 0
    assert result.metadata.outside_mask_changed_pixel_percent == 0
    assert result.metadata.hard_mask_coverage_percent > 1.0
    assert result.metadata.tile_size >= 32


def test_local_texture_transfer_preserves_original_luminance_variation_inside_mask(tmp_path: Path) -> None:
    source, fabric, mask = _paths(tmp_path)

    result = transfer_fabric_texture_locally(
        original_image_path=source,
        fabric_reference_path=fabric,
        mask_image_path=mask,
        min_coverage_percent=1.0,
        max_coverage_percent=80.0,
        shadow_strength=0.9,
    )

    output_path = tmp_path / "output.png"
    output_path.write_bytes(result.image_bytes)
    with Image.open(output_path) as output:
        luma = output.convert("L")
        dark_fold = luma.getpixel((58, 100))
        light_fold = luma.getpixel((84, 100))
    assert abs(int(light_fold) - int(dark_fold)) >= 12


def test_local_texture_transfer_rejects_mask_size_mismatch(tmp_path: Path) -> None:
    source, fabric, _mask = _paths(tmp_path)
    bad_mask = tmp_path / "bad-mask.png"
    Image.new("RGBA", (120, 160), color=(0, 0, 0, 0)).save(bad_mask)

    with pytest.raises(LocalTextureTransferError, match="Mask size"):
        transfer_fabric_texture_locally(
            original_image_path=source,
            fabric_reference_path=fabric,
            mask_image_path=bad_mask,
            min_coverage_percent=1.0,
            max_coverage_percent=80.0,
        )


def test_local_texture_transfer_rejects_empty_mask(tmp_path: Path) -> None:
    source, fabric, _mask = _paths(tmp_path)
    empty_mask = tmp_path / "empty-mask.png"
    Image.new("RGBA", (160, 200), color=(0, 0, 0, 255)).save(empty_mask)

    with pytest.raises(LocalTextureTransferError, match="no editable"):
        transfer_fabric_texture_locally(
            original_image_path=source,
            fabric_reference_path=fabric,
            mask_image_path=empty_mask,
            min_coverage_percent=1.0,
            max_coverage_percent=80.0,
        )
