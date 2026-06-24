"""Optional user-photo edit mask preparation and validation."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageDraw, ImageFilter, UnidentifiedImageError

from app.config import get_settings
from app.services.storage_service import resolve_upload_path

MASK_FOLDER = "user-photo-masks"
EDITABLE_ALPHA_THRESHOLD = 128
MASK_PRESET_CENTRAL_UPPER_GARMENT = "central_upper_garment"
MASK_PRESET_VISIBLE_INNER_TSHIRT = "visible_inner_tshirt"
MASK_PRESET_OPEN_OVERSHIRT_INNER_GARMENT = "open_overshirt_inner_garment"
ALLOWED_MASK_PRESETS = {
    MASK_PRESET_CENTRAL_UPPER_GARMENT,
    MASK_PRESET_VISIBLE_INNER_TSHIRT,
    MASK_PRESET_OPEN_OVERSHIRT_INNER_GARMENT,
}
GENERATED_MASK_LEFT_RATIO = 0.34
GENERATED_MASK_TOP_RATIO = 0.36
GENERATED_MASK_RIGHT_RATIO = 0.66
GENERATED_MASK_BOTTOM_RATIO = 0.68
ALLOWED_MASK_MODES = {"off", "provided", "mock", "provider"}
STRICT_MASK_REQUIRED_MESSAGE = "Для точной примерки нужна маска области одежды."
MASK_PROVIDER_NOT_CONFIGURED_MESSAGE = "Clothing mask provider is not configured yet."
INVALID_MASK_PRESET_MESSAGE = "Unsupported user photo mask preset."

MASK_ERROR_MESSAGES = {
    "path_traversal": "Mask path is unsafe.",
    "missing_file": "Mask file is missing.",
    "empty_file": "Mask file is empty.",
    "not_png": "Mask must be a PNG image.",
    "unreadable_image": "Mask file cannot be decoded.",
    "missing_alpha": "Mask must include alpha transparency.",
    "size_mismatch": "Mask size must match the user photo.",
    "empty_mask": "Mask has no editable transparent region.",
    "tiny_coverage": "Mask editable region is too small.",
    "full_image_mask": "Mask cannot edit the full image.",
    "excessive_coverage": "Mask editable region is too large.",
}


@dataclass
class MaskReadiness:
    ready: bool = False
    error_code: str | None = None
    error_message: str | None = None
    width: int | None = None
    height: int | None = None
    base_width: int | None = None
    base_height: int | None = None
    coverage_percent: float | None = None

    def mark_error(self, code: str) -> "MaskReadiness":
        self.ready = False
        self.error_code = code
        self.error_message = MASK_ERROR_MESSAGES.get(code, "Mask is not ready.")
        return self


@dataclass
class MaskResult:
    mask_image_url: str
    mask_path: Path
    readiness: MaskReadiness
    mode: str


def _safe_existing_upload_path(path: Path) -> Path:
    upload_root = get_settings().upload_dir.resolve()
    target = Path(path).resolve()
    if upload_root != target and upload_root not in target.parents:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Mask path is unsafe.")
    if not target.exists() or not target.is_file():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Mask file is missing.")
    return target


def _has_alpha(image: Image.Image) -> bool:
    return image.mode in {"RGBA", "LA"} or "transparency" in image.info


def _load_base_size(base_image_path: Path) -> tuple[int, int]:
    try:
        with Image.open(_safe_existing_upload_path(base_image_path)) as base_image:
            return base_image.size
    except (OSError, SyntaxError, UnidentifiedImageError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User photo file is not readable.") from exc


def calculate_edit_coverage(mask_path: Path) -> float:
    """Return percent of transparent/editable pixels in an OpenAI edit mask."""

    with Image.open(mask_path) as image:
        mask_image = image.convert("RGBA")
        alpha = mask_image.getchannel("A")
        total_pixels = mask_image.width * mask_image.height
        if total_pixels <= 0:
            return 0.0
        editable_pixels = sum(alpha.histogram()[:EDITABLE_ALPHA_THRESHOLD])
        return editable_pixels / total_pixels * 100


def validate_edit_mask(mask_path: Path, base_image_path: Path) -> MaskReadiness:
    """Validate a PNG edit mask for one user photo without leaking server paths."""

    readiness = MaskReadiness()
    try:
        safe_mask_path = _safe_existing_upload_path(mask_path)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else ""
        if "unsafe" in detail:
            return readiness.mark_error("path_traversal")
        return readiness.mark_error("missing_file")

    if safe_mask_path.stat().st_size <= 0:
        return readiness.mark_error("empty_file")
    if safe_mask_path.suffix.lower() != ".png":
        return readiness.mark_error("not_png")

    try:
        base_width, base_height = _load_base_size(base_image_path)
        with Image.open(safe_mask_path) as image:
            if image.format != "PNG":
                return readiness.mark_error("not_png")
            if not _has_alpha(image):
                return readiness.mark_error("missing_alpha")
            mask_image = image.convert("RGBA")
            readiness.width, readiness.height = mask_image.size
            readiness.base_width, readiness.base_height = base_width, base_height
    except HTTPException:
        raise
    except (OSError, SyntaxError, UnidentifiedImageError):
        return readiness.mark_error("unreadable_image")

    if (readiness.width, readiness.height) != (readiness.base_width, readiness.base_height):
        return readiness.mark_error("size_mismatch")

    try:
        readiness.coverage_percent = calculate_edit_coverage(safe_mask_path)
    except (OSError, SyntaxError, UnidentifiedImageError):
        return readiness.mark_error("unreadable_image")

    min_coverage = get_settings().user_photo_mask_min_coverage_percent
    max_coverage = get_settings().user_photo_mask_max_coverage_percent
    coverage = readiness.coverage_percent or 0.0
    if coverage <= 0:
        return readiness.mark_error("empty_mask")
    if coverage < min_coverage:
        return readiness.mark_error("tiny_coverage")
    if coverage >= 100:
        return readiness.mark_error("full_image_mask")
    if coverage > max_coverage:
        return readiness.mark_error("excessive_coverage")

    readiness.ready = True
    return readiness


def ensure_mask_matches_base(mask_path: Path, base_image_path: Path) -> None:
    """Raise a controlled error when a mask is not usable for the base image."""

    readiness = validate_edit_mask(mask_path, base_image_path)
    if not readiness.ready:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User photo mask is not valid for editing.")


def save_mask_image(mask_bytes: bytes) -> str:
    """Persist validated mask bytes as a normalized PNG and return a public upload URL."""

    if not mask_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Mask file is empty.")
    if len(mask_bytes) > get_settings().max_upload_size_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Mask file is too large.")
    try:
        with Image.open(BytesIO(mask_bytes)) as image:
            if image.format != "PNG":
                raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Mask must be a PNG image.")
            normalized = image.convert("RGBA")
    except HTTPException:
        raise
    except (OSError, SyntaxError, UnidentifiedImageError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Mask file cannot be decoded.") from exc

    target_dir = get_settings().upload_dir / MASK_FOLDER
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}.png"
    target_path = target_dir / filename
    normalized.save(target_path, format="PNG")
    return f"/uploads/{MASK_FOLDER}/{filename}"


def _mock_mask_bytes(base_image_path: Path) -> bytes:
    width, height = _load_base_size(base_image_path)
    mask = Image.new("RGBA", (width, height), color=(0, 0, 0, 255))
    left = max(0, int(width * GENERATED_MASK_LEFT_RATIO))
    top = max(0, int(height * GENERATED_MASK_TOP_RATIO))
    right = min(width, int(width * GENERATED_MASK_RIGHT_RATIO))
    bottom = min(height, int(height * GENERATED_MASK_BOTTOM_RATIO))
    ImageDraw.Draw(mask).rectangle((left, top, right, bottom), fill=(0, 0, 0, 0))
    buffer = BytesIO()
    mask.save(buffer, format="PNG")
    return buffer.getvalue()


def _central_upper_garment_mask(base_image_path: Path) -> Image.Image:
    width, height = _load_base_size(base_image_path)
    if width < 160 or height < 160:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User photo is too small for preset mask editing.")

    mask = Image.new("RGBA", (width, height), color=(0, 0, 0, 255))
    draw = ImageDraw.Draw(mask)
    left = int(width * 0.32)
    right = int(width * 0.68)
    top = int(height * 0.38)
    bottom = int(height * 0.72)
    shoulder_inset = int(width * 0.04)
    lower_inset = int(width * 0.02)
    points = [
        (left + shoulder_inset, top),
        (right - shoulder_inset, top),
        (right, int(height * 0.50)),
        (right - lower_inset, bottom),
        (left + lower_inset, bottom),
        (left, int(height * 0.50)),
    ]
    draw.polygon(points, fill=(0, 0, 0, 0))
    return mask


def _visible_inner_tshirt_mask(base_image_path: Path) -> Image.Image:
    """Create a conservative mask for a light inner T-shirt under an open overshirt.

    This deterministic preset is intentionally narrow. It targets a common
    mirror-selfie case where a light inner garment is visible in the center and
    a darker/colorful overshirt, hands, phone, face, and background must stay
    protected. Low-confidence photos fail later through normal mask coverage
    validation instead of falling back to a broad rectangle.
    """

    try:
        with Image.open(_safe_existing_upload_path(base_image_path)) as image:
            rgb = image.convert("RGB")
    except (OSError, SyntaxError, UnidentifiedImageError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User photo file is not readable.") from exc

    width, height = rgb.size
    if width < 160 or height < 160:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User photo is too small for preset mask editing.")

    alpha = Image.new("L", (width, height), color=255)
    pixels = rgb.load()
    left = int(width * 0.30)
    right = int(width * 0.70)
    top = int(height * 0.34)
    bottom = int(height * 0.74)
    center_x = width / 2
    half_width = max(1, (right - left) / 2)

    for y in range(top, bottom):
        y_progress = (y - top) / max(1, bottom - top)
        # Slight hourglass shape: avoid arms/open overshirt at shoulders and lower sides.
        allowed_half_ratio = 0.42 + 0.26 * min(1.0, y_progress * 1.4)
        for x in range(left, right):
            normalized_x = abs(x - center_x) / half_width
            if normalized_x > allowed_half_ratio:
                continue
            red, green, blue = pixels[x, y]
            brightness = (red + green + blue) / 3
            chroma = max(red, green, blue) - min(red, green, blue)
            # Target light/neutral fabric. This deliberately excludes saturated green/blue overshirts,
            # skin, dark phones, and most backgrounds.
            if brightness >= 138 and chroma <= 78 and red >= 120 and green >= 120 and blue >= 112:
                alpha.putpixel((x, y), 0)

    # Expand tiny gaps inside the detected fabric, then restore a little edge softness.
    alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
    mask = Image.new("RGBA", (width, height), color=(0, 0, 0, 255))
    mask.putalpha(alpha)
    return mask


def _preset_mask_bytes(base_image_path: Path, preset: str) -> bytes:
    if preset == MASK_PRESET_CENTRAL_UPPER_GARMENT:
        mask = _central_upper_garment_mask(base_image_path)
    elif preset in {MASK_PRESET_VISIBLE_INNER_TSHIRT, MASK_PRESET_OPEN_OVERSHIRT_INNER_GARMENT}:
        mask = _visible_inner_tshirt_mask(base_image_path)
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, INVALID_MASK_PRESET_MESSAGE)

    buffer = BytesIO()
    mask.save(buffer, format="PNG")
    return buffer.getvalue()


def prepare_user_photo_preset_mask(base_image_path: Path, preset: str) -> MaskResult:
    """Create and validate a conservative explicit preset mask for one user photo."""

    normalized_preset = preset.strip().lower()
    if normalized_preset not in ALLOWED_MASK_PRESETS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, INVALID_MASK_PRESET_MESSAGE)

    mask_url = save_mask_image(_preset_mask_bytes(base_image_path, normalized_preset))
    mask_path = resolve_upload_path(mask_url)
    readiness = validate_edit_mask(mask_path, base_image_path)
    if not readiness.ready:
        try:
            mask_path.unlink()
        except OSError:
            pass
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Preset clothing mask is not valid for editing.")
    return MaskResult(mask_image_url=mask_url, mask_path=mask_path, readiness=readiness, mode=f"preset:{normalized_preset}")


def _mask_mode() -> str:
    mode = get_settings().user_photo_mask_mode.strip().lower()
    return mode if mode in ALLOWED_MASK_MODES else "off"


async def prepare_user_photo_mask(
    base_image_path: Path,
    provided_mask: UploadFile | None = None,
    *,
    allow_generated_mask: bool = False,
) -> MaskResult | None:
    """Prepare an optional edit mask according to USER_PHOTO_MASK_MODE."""

    mode = _mask_mode()
    settings = get_settings()
    if mode == "off":
        if provided_mask is not None:
            if (provided_mask.content_type or "").lower() != "image/png":
                raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Mask must be a PNG image.")
            mask_bytes = await provided_mask.read()
            mode = "provided"
        elif allow_generated_mask and settings.user_photo_require_mask_for_strict_edit and not settings.is_production_like:
            mask_bytes = _mock_mask_bytes(base_image_path)
            mode = "generated"
        else:
            if settings.user_photo_require_mask_for_strict_edit:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, STRICT_MASK_REQUIRED_MESSAGE)
            return None
    elif mode == "provider":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, MASK_PROVIDER_NOT_CONFIGURED_MESSAGE)
    elif mode == "provided":
        if provided_mask is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, STRICT_MASK_REQUIRED_MESSAGE)
        if (provided_mask.content_type or "").lower() != "image/png":
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Mask must be a PNG image.")
        mask_bytes = await provided_mask.read()
    else:
        if settings.is_production_like:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, STRICT_MASK_REQUIRED_MESSAGE)
        mask_bytes = _mock_mask_bytes(base_image_path)

    mask_url = save_mask_image(mask_bytes)
    mask_path = resolve_upload_path(mask_url)
    readiness = validate_edit_mask(mask_path, base_image_path)
    if not readiness.ready:
        try:
            mask_path.unlink()
        except OSError:
            pass
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User photo mask is not valid for editing.")
    return MaskResult(mask_image_url=mask_url, mask_path=mask_path, readiness=readiness, mode=mode)
