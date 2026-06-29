"""Deterministic local fabric transfer for masked user-photo try-on."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageStat, UnidentifiedImageError


LOCAL_TEXTURE_TRANSFER_VERSION = "local_texture_transfer_v1"


@dataclass(frozen=True)
class LocalTextureTransferMetadata:
    """Sanitized metadata for local texture-transfer attempts."""

    local_transfer_version: str
    provider_called: bool
    original_size: tuple[int, int]
    mask_size: tuple[int, int]
    fabric_reference_size: tuple[int, int]
    hard_mask_coverage_percent: float
    editable_bounds: tuple[int, int, int, int]
    tile_size: int
    feather_radius: int
    shadow_strength: float
    saturation_strength: float
    blend_mode: str
    outside_mask_mean_delta: float
    outside_mask_changed_pixel_percent: float

    def as_dict(self) -> dict[str, object]:
        return {
            "local_transfer_version": self.local_transfer_version,
            "provider_called": self.provider_called,
            "original_size": list(self.original_size),
            "mask_size": list(self.mask_size),
            "fabric_reference_size": list(self.fabric_reference_size),
            "hard_mask_coverage_percent": self.hard_mask_coverage_percent,
            "editable_bounds": list(self.editable_bounds),
            "tile_size": self.tile_size,
            "feather_radius": self.feather_radius,
            "shadow_strength": self.shadow_strength,
            "saturation_strength": self.saturation_strength,
            "blend_mode": self.blend_mode,
            "outside_mask_mean_delta": self.outside_mask_mean_delta,
            "outside_mask_changed_pixel_percent": self.outside_mask_changed_pixel_percent,
        }


@dataclass(frozen=True)
class LocalTextureTransferResult:
    image_bytes: bytes
    metadata: LocalTextureTransferMetadata


class LocalTextureTransferError(ValueError):
    """Raised when deterministic local texture transfer cannot run safely."""


def _load_rgb(path: Path, message: str) -> Image.Image:
    try:
        with Image.open(path) as image:
            return image.convert("RGB").copy()
    except (OSError, SyntaxError, UnidentifiedImageError) as exc:
        raise LocalTextureTransferError(message) from exc


def _load_mask(path: Path) -> Image.Image:
    try:
        with Image.open(path) as image:
            return image.convert("RGBA").copy()
    except (OSError, SyntaxError, UnidentifiedImageError) as exc:
        raise LocalTextureTransferError("Mask image is not readable.") from exc


def _editable_mask(mask_image: Image.Image) -> Image.Image:
    alpha = mask_image.getchannel("A")
    # Provider/local convention: transparent pixels are editable.
    return alpha.point(lambda value: 255 if value < 128 else 0, mode="L")


def _coverage_percent(mask: Image.Image) -> float:
    extrema = mask.getextrema()
    if extrema == (0, 0):
        return 0.0
    histogram = mask.histogram()
    editable_pixels = sum(histogram[1:])
    return editable_pixels / max(1, mask.width * mask.height) * 100


def _center_square(image: Image.Image) -> Image.Image:
    side = min(image.width, image.height)
    left = (image.width - side) // 2
    top = (image.height - side) // 2
    return image.crop((left, top, left + side, top + side))


def _default_tile_size(bounds: tuple[int, int, int, int]) -> int:
    left, top, right, bottom = bounds
    garment_width = max(1, right - left)
    garment_height = max(1, bottom - top)
    return max(96, min(384, max(garment_width, garment_height) // 2))


def _tile_fabric(fabric: Image.Image, canvas_size: tuple[int, int], tile_size: int) -> Image.Image:
    tile = _center_square(fabric).resize((tile_size, tile_size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", canvas_size)
    for y in range(0, canvas.height, tile_size):
        for x in range(0, canvas.width, tile_size):
            canvas.paste(tile, (x, y))
    return canvas


def _apply_original_shading(
    *,
    original: Image.Image,
    fabric_canvas: Image.Image,
    editable_mask: Image.Image,
    shadow_strength: float,
) -> Image.Image:
    luminance = original.convert("L").filter(ImageFilter.GaussianBlur(radius=2))
    stat = ImageStat.Stat(luminance, mask=editable_mask)
    mean_luminance = stat.mean[0] if stat.count[0] else 128.0
    mean_luminance = max(1.0, mean_luminance)
    strength = max(0.0, min(1.5, shadow_strength))

    def shade_point(value: int) -> int:
        ratio = value / mean_luminance
        shade = 255 * (1.0 - strength + strength * ratio)
        return max(0, min(255, int(round(shade))))

    shade = luminance.point(shade_point, mode="L")
    shade_rgb = Image.merge("RGB", (shade, shade, shade))
    return ImageChops.multiply(fabric_canvas, shade_rgb)


def _soft_mask_inside_hard_mask(editable_mask: Image.Image, feather_radius: int) -> Image.Image:
    if feather_radius <= 0:
        return editable_mask
    softened = editable_mask.filter(ImageFilter.GaussianBlur(radius=feather_radius))
    # Multiplying by the hard mask keeps protected pixels exactly unchanged.
    return ImageChops.multiply(softened, editable_mask)


def _outside_mask_metrics(original: Image.Image, candidate: Image.Image, editable_mask: Image.Image) -> tuple[float, float]:
    protected_mask = editable_mask.point(lambda value: 255 if value == 0 else 0, mode="L")
    diff = ImageChops.difference(original, candidate).convert("RGB")
    stat = ImageStat.Stat(diff, mask=protected_mask)
    protected_pixels = stat.count[0]
    if protected_pixels <= 0:
        return 0.0, 0.0
    mean_delta = sum(stat.mean) / 3

    changed = 0
    diff_pixels = diff.load()
    mask_pixels = protected_mask.load()
    for y in range(diff.height):
        for x in range(diff.width):
            if mask_pixels[x, y] and max(diff_pixels[x, y]) > 0:
                changed += 1
    changed_percent = changed / protected_pixels * 100
    return mean_delta, changed_percent


def transfer_fabric_texture_locally(
    *,
    original_image_path: Path,
    fabric_reference_path: Path,
    mask_image_path: Path,
    min_coverage_percent: float,
    max_coverage_percent: float,
    texture_scale: int | None = None,
    feather_radius: int = 4,
    shadow_strength: float = 0.85,
    saturation_strength: float = 1.0,
    blend_mode: str = "fabric_rgb_with_original_luminance",
) -> LocalTextureTransferResult:
    """Retexture only transparent mask pixels without calling a provider."""

    original = _load_rgb(original_image_path, "User photo is not readable.")
    fabric = _load_rgb(fabric_reference_path, "Fabric reference image is not readable.")
    mask_rgba = _load_mask(mask_image_path)

    if mask_rgba.size != original.size:
        raise LocalTextureTransferError("Mask size must match user photo size.")

    hard_mask = _editable_mask(mask_rgba)
    coverage = _coverage_percent(hard_mask)
    if coverage <= 0:
        raise LocalTextureTransferError("Mask has no editable clothing pixels.")
    if coverage < min_coverage_percent or coverage > max_coverage_percent:
        raise LocalTextureTransferError("Mask editable coverage is outside the safe range.")
    bounds = hard_mask.getbbox()
    if bounds is None:
        raise LocalTextureTransferError("Mask has no editable clothing pixels.")

    tile_size = texture_scale or _default_tile_size(bounds)
    tile_size = max(32, min(768, int(tile_size)))
    fabric_canvas = _tile_fabric(fabric, original.size, tile_size)
    shaded_fabric = _apply_original_shading(
        original=original,
        fabric_canvas=fabric_canvas,
        editable_mask=hard_mask,
        shadow_strength=shadow_strength,
    )
    soft_mask = _soft_mask_inside_hard_mask(hard_mask, max(0, int(feather_radius)))
    candidate = Image.composite(shaded_fabric, original, soft_mask)

    outside_mean_delta, outside_changed_percent = _outside_mask_metrics(original, candidate, hard_mask)
    buffer = BytesIO()
    candidate.save(buffer, format="PNG")
    metadata = LocalTextureTransferMetadata(
        local_transfer_version=LOCAL_TEXTURE_TRANSFER_VERSION,
        provider_called=False,
        original_size=original.size,
        mask_size=mask_rgba.size,
        fabric_reference_size=fabric.size,
        hard_mask_coverage_percent=coverage,
        editable_bounds=bounds,
        tile_size=tile_size,
        feather_radius=max(0, int(feather_radius)),
        shadow_strength=shadow_strength,
        saturation_strength=saturation_strength,
        blend_mode=blend_mode,
        outside_mask_mean_delta=outside_mean_delta,
        outside_mask_changed_pixel_percent=outside_changed_percent,
    )
    return LocalTextureTransferResult(image_bytes=buffer.getvalue(), metadata=metadata)
