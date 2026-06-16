"""Optional user-photo edit mask preparation and validation."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageDraw, UnidentifiedImageError

from app.config import get_settings
from app.services.storage_service import resolve_upload_path

MASK_FOLDER = "user-photo-masks"
EDITABLE_ALPHA_THRESHOLD = 128
ALLOWED_MASK_MODES = {"off", "provided", "mock", "provider"}

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
    left = max(0, int(width * 0.25))
    top = max(0, int(height * 0.25))
    right = min(width, int(width * 0.75))
    bottom = min(height, int(height * 0.85))
    ImageDraw.Draw(mask).rectangle((left, top, right, bottom), fill=(0, 0, 0, 0))
    buffer = BytesIO()
    mask.save(buffer, format="PNG")
    return buffer.getvalue()


def _mask_mode() -> str:
    mode = get_settings().user_photo_mask_mode.strip().lower()
    return mode if mode in ALLOWED_MASK_MODES else "off"


async def prepare_user_photo_mask(base_image_path: Path, provided_mask: UploadFile | None = None) -> MaskResult | None:
    """Prepare an optional edit mask according to USER_PHOTO_MASK_MODE."""

    mode = _mask_mode()
    if mode in {"off", "provider"}:
        return None
    if mode == "provided":
        if provided_mask is None:
            return None
        if (provided_mask.content_type or "").lower() != "image/png":
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Mask must be a PNG image.")
        mask_bytes = await provided_mask.read()
    else:
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
