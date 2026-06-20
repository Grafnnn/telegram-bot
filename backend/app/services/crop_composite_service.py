"""Deterministic crop/composite helpers for local user-photo try-on rehearsals.

These helpers do not call providers and do not touch storage. They implement
the crop-local mechanics described by the segmentation-first crop/composite
strategy so tests can prove the geometry before any future provider gate.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

EDITABLE_ALPHA_THRESHOLD = 128


@dataclass(frozen=True)
class CropBox:
    """Pillow-compatible crop box with exclusive right/bottom bounds."""

    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def pil_box(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.right, self.bottom)


@dataclass(frozen=True)
class CropInputs:
    """Crop-local source and mask prepared for a future provider call."""

    crop_box: CropBox
    source_crop: Image.Image
    mask_crop: Image.Image


def _ensure_same_size(source_image: Image.Image, mask_image: Image.Image) -> None:
    if source_image.size != mask_image.size:
        raise ValueError(
            "Crop/composite source and mask dimensions must match: "
            f"source_image={source_image.width}x{source_image.height}, "
            f"mask_image={mask_image.width}x{mask_image.height}"
        )


def _validate_crop_box(crop_box: CropBox, image_size: tuple[int, int]) -> None:
    width, height = image_size
    if crop_box.left < 0 or crop_box.top < 0 or crop_box.right > width or crop_box.bottom > height:
        raise ValueError("Crop box must be inside source image bounds.")
    if crop_box.width <= 0 or crop_box.height <= 0:
        raise ValueError("Crop box must have positive dimensions.")


def _editable_mask(alpha: Image.Image, *, editable_alpha_threshold: int = EDITABLE_ALPHA_THRESHOLD) -> Image.Image:
    return alpha.point(lambda value: 255 if value < editable_alpha_threshold else 0, mode="L")


def find_editable_crop_box(
    mask_image: Image.Image,
    *,
    padding_pixels: int = 0,
    editable_alpha_threshold: int = EDITABLE_ALPHA_THRESHOLD,
) -> CropBox:
    """Return a padded crop box around transparent/editable mask pixels."""

    if padding_pixels < 0:
        raise ValueError("Crop padding must be non-negative.")
    mask_rgba = mask_image.convert("RGBA")
    editable = _editable_mask(mask_rgba.getchannel("A"), editable_alpha_threshold=editable_alpha_threshold)
    bbox = editable.getbbox()
    if bbox is None:
        raise ValueError("Mask has no editable pixels.")

    left, top, right, bottom = bbox
    width, height = mask_rgba.size
    crop_box = CropBox(
        left=max(0, left - padding_pixels),
        top=max(0, top - padding_pixels),
        right=min(width, right + padding_pixels),
        bottom=min(height, bottom + padding_pixels),
    )
    _validate_crop_box(crop_box, mask_rgba.size)
    return crop_box


def prepare_crop_inputs(
    source_image: Image.Image,
    mask_image: Image.Image,
    *,
    padding_pixels: int = 0,
    editable_alpha_threshold: int = EDITABLE_ALPHA_THRESHOLD,
) -> CropInputs:
    """Build crop-local source and mask images from a full source/mask pair."""

    _ensure_same_size(source_image, mask_image)
    crop_box = find_editable_crop_box(
        mask_image,
        padding_pixels=padding_pixels,
        editable_alpha_threshold=editable_alpha_threshold,
    )
    return CropInputs(
        crop_box=crop_box,
        source_crop=source_image.convert("RGB").crop(crop_box.pil_box),
        mask_crop=mask_image.convert("RGBA").crop(crop_box.pil_box),
    )


def composite_edited_crop(
    source_image: Image.Image,
    edited_crop: Image.Image,
    mask_image: Image.Image,
    crop_box: CropBox,
    *,
    editable_alpha_threshold: int = EDITABLE_ALPHA_THRESHOLD,
) -> Image.Image:
    """Composite edited crop pixels back only inside transparent mask pixels."""

    _ensure_same_size(source_image, mask_image)
    _validate_crop_box(crop_box, source_image.size)
    if edited_crop.size != (crop_box.width, crop_box.height):
        raise ValueError(
            "Edited crop dimensions must match crop box: "
            f"edited_crop={edited_crop.width}x{edited_crop.height}, crop_box={crop_box.width}x{crop_box.height}"
        )

    source_rgb = source_image.convert("RGB")
    edited_rgb = edited_crop.convert("RGB")
    mask_crop = mask_image.convert("RGBA").crop(crop_box.pil_box)
    paste_mask = _editable_mask(mask_crop.getchannel("A"), editable_alpha_threshold=editable_alpha_threshold)

    result = source_rgb.copy()
    result.paste(edited_rgb, (crop_box.left, crop_box.top), paste_mask)
    return result
