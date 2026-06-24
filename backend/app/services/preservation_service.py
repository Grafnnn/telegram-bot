"""Helpers for measuring user-photo preservation outside an edit mask.

The user-photo mask convention matches OpenAI image edit masks used elsewhere
in the backend: transparent pixels are editable, and opaque pixels are expected
protected. These helpers are intentionally local/deterministic and do not call
providers or inspect secrets.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

EDITABLE_ALPHA_THRESHOLD = 128
DEFAULT_PIXEL_DELTA_THRESHOLD = 8
PRESERVATION_FAILURE_MESSAGE = "Generated image changed protected regions outside the clothing mask."
PRESERVATION_FAILURE_USER_MESSAGE = (
    "Не удалось безопасно сохранить исходное фото вне области одежды. Попробуйте другое фото или маску."
)


@dataclass(frozen=True)
class OutsideMaskDrift:
    """Summary of RGB drift in protected, non-editable pixels."""

    protected_pixel_count: int
    editable_pixel_count: int
    mean_delta: float
    max_delta: int
    changed_pixel_count: int
    changed_pixel_percent: float
    pixel_delta_threshold: int

    def passes(self, *, max_mean_delta: float, max_changed_pixel_percent: float) -> bool:
        """Return whether this metric satisfies conservative caller thresholds."""

        return self.mean_delta <= max_mean_delta and self.changed_pixel_percent <= max_changed_pixel_percent


@dataclass(frozen=True)
class PreservationThresholds:
    """Thresholds used to decide whether protected pixels remained stable."""

    max_mean_delta: float = 1.0
    max_changed_pixel_percent: float = 1.0
    pixel_delta_threshold: int = DEFAULT_PIXEL_DELTA_THRESHOLD


@dataclass(frozen=True)
class PreservationCheckResult:
    """Outcome of a post-generation preservation guardrail check."""

    passes: bool
    reason: str | None
    message: str
    thresholds: PreservationThresholds
    drift: OutsideMaskDrift | None = None
    metadata: "PreservationImageMetadata | None" = None
    normalized_candidate_image_bytes: bytes | None = None


@dataclass(frozen=True)
class PreservationImageMetadata:
    """Sanitized image geometry metadata for debugging preservation decisions."""

    original_size: tuple[int, int] | None
    mask_size: tuple[int, int] | None
    provider_output_size: tuple[int, int] | None
    normalized_output_size: tuple[int, int] | None
    aspect_ratio_delta: float | None
    size_normalized: bool
    reject_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe metadata with no paths or binary payloads."""

        data = asdict(self)
        for key in ("original_size", "mask_size", "provider_output_size", "normalized_output_size"):
            value = data[key]
            data[key] = list(value) if value else None
        return data


class UserPhotoPreservationError(RuntimeError):
    """Raised when a provider output is not safe to expose as successful."""

    def __init__(self, result: PreservationCheckResult) -> None:
        super().__init__(PRESERVATION_FAILURE_USER_MESSAGE)
        self.result = result


def _pixel_data(image: Image.Image):
    get_flattened_data = getattr(image, "get_flattened_data", None)
    return get_flattened_data() if get_flattened_data else image.getdata()


def _ensure_same_size(base_image: Image.Image, candidate_image: Image.Image, mask_image: Image.Image) -> None:
    sizes = {
        "base_image": base_image.size,
        "candidate_image": candidate_image.size,
        "mask_image": mask_image.size,
    }
    unique_sizes = set(sizes.values())
    if len(unique_sizes) == 1:
        return
    details = ", ".join(f"{name}={width}x{height}" for name, (width, height) in sizes.items())
    raise ValueError(f"Preservation drift inputs must have matching dimensions: {details}")


def _changed_pixel_bounds(
    base_image: Image.Image,
    candidate_image: Image.Image,
    *,
    pixel_delta_threshold: int,
) -> tuple[int, int, int, int, int] | None:
    """Return the bounding box and count for visibly changed pixels."""

    base_rgb = base_image.convert("RGB")
    candidate_rgb = candidate_image.convert("RGB")
    min_x = base_rgb.width
    min_y = base_rgb.height
    max_x = -1
    max_y = -1
    changed_count = 0
    for index, (base_pixel, candidate_pixel) in enumerate(
        zip(_pixel_data(base_rgb), _pixel_data(candidate_rgb), strict=True)
    ):
        delta = max(abs(int(left) - int(right)) for left, right in zip(base_pixel, candidate_pixel, strict=True))
        if delta <= pixel_delta_threshold:
            continue
        x = index % base_rgb.width
        y = index // base_rgb.width
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x)
        max_y = max(max_y, y)
        changed_count += 1
    if changed_count <= 0:
        return None
    return min_x, min_y, max_x, max_y, changed_count


def _editable_mask_fill_ratio(mask_image: Image.Image, *, editable_alpha_threshold: int = EDITABLE_ALPHA_THRESHOLD) -> float:
    """Return how rectangular the editable mask region is inside its own bounds."""

    alpha = mask_image.convert("RGBA").getchannel("A")
    min_x = alpha.width
    min_y = alpha.height
    max_x = -1
    max_y = -1
    editable_count = 0
    for index, alpha_value in enumerate(_pixel_data(alpha)):
        if alpha_value >= editable_alpha_threshold:
            continue
        x = index % alpha.width
        y = index // alpha.width
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x)
        max_y = max(max_y, y)
        editable_count += 1
    if editable_count <= 0:
        return 0.0
    bbox_area = (max_x - min_x + 1) * (max_y - min_y + 1)
    return editable_count / bbox_area if bbox_area else 0.0


def _looks_like_rectangular_overlay(
    base_image: Image.Image,
    candidate_image: Image.Image,
    mask_image: Image.Image,
    *,
    pixel_delta_threshold: int,
) -> bool:
    """Detect large hard-edged rectangular paste/collage artifacts.

    This is intentionally conservative: it targets outputs where most changed
    pixels fill one large axis-aligned rectangle while the editable mask itself
    is not rectangular. Normal masked edits that follow a shirt/polygon mask do
    not fill the entire mask bounding box and therefore pass this heuristic.
    """

    bounds = _changed_pixel_bounds(base_image, candidate_image, pixel_delta_threshold=pixel_delta_threshold)
    if bounds is None:
        return False
    min_x, min_y, max_x, max_y, changed_count = bounds
    bbox_width = max_x - min_x + 1
    bbox_height = max_y - min_y + 1
    bbox_area = bbox_width * bbox_height
    total_area = base_image.width * base_image.height
    if total_area <= 0 or bbox_area <= 0:
        return False
    if bbox_area / total_area < 0.04:
        return False
    changed_fill_ratio = changed_count / bbox_area
    if changed_fill_ratio < 0.86:
        return False
    mask_fill_ratio = _editable_mask_fill_ratio(mask_image)
    return mask_fill_ratio < 0.86


def _load_image_copy(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return image.copy()


def _load_candidate_bytes(candidate_image_bytes: bytes) -> Image.Image:
    if not candidate_image_bytes:
        raise ValueError("Generated image is empty.")
    with Image.open(BytesIO(candidate_image_bytes)) as image:
        return image.copy()


def _image_to_png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _aspect_ratio(size: tuple[int, int]) -> float:
    width, height = size
    return width / height if height else 0.0


def _can_normalize_full_frame_candidate(
    *,
    original_size: tuple[int, int],
    candidate_size: tuple[int, int],
    aspect_ratio_delta: float,
) -> bool:
    """Return whether a provider output can be safely resized for comparison.

    The provider may return a valid full-frame edit at a different pixel size.
    We only normalize when the aspect ratio is effectively the same and the
    candidate is not a tiny thumbnail/crop. Different-aspect outputs remain a
    hard fail because resizing them would hide crop/letterbox/paste artifacts.
    """

    if candidate_size == original_size:
        return True
    original_width, original_height = original_size
    candidate_width, candidate_height = candidate_size
    if min(original_size) <= 0 or min(candidate_size) <= 0:
        return False
    if aspect_ratio_delta > 0.01:
        return False
    width_ratio = candidate_width / original_width
    height_ratio = candidate_height / original_height
    # Avoid treating 1x1 or tiny thumbnails as full-frame provider results.
    return width_ratio >= 0.5 and height_ratio >= 0.5


def calculate_outside_mask_drift(
    base_image: Image.Image,
    candidate_image: Image.Image,
    mask_image: Image.Image,
    *,
    editable_alpha_threshold: int = EDITABLE_ALPHA_THRESHOLD,
    pixel_delta_threshold: int = DEFAULT_PIXEL_DELTA_THRESHOLD,
) -> OutsideMaskDrift:
    """Measure RGB drift outside the editable mask region.

    Transparent mask pixels are editable. Opaque pixels are protected and should
    remain visually stable. The per-pixel delta is the maximum absolute RGB
    channel difference for that protected pixel, which makes large color shifts
    easy to detect without adding a numeric dependency.
    """

    _ensure_same_size(base_image, candidate_image, mask_image)

    base_rgb = base_image.convert("RGB")
    candidate_rgb = candidate_image.convert("RGB")
    alpha = mask_image.convert("RGBA").getchannel("A")

    protected_pixel_count = 0
    editable_pixel_count = 0
    changed_pixel_count = 0
    total_delta = 0
    max_delta = 0

    for base_pixel, candidate_pixel, alpha_value in zip(
        _pixel_data(base_rgb),
        _pixel_data(candidate_rgb),
        _pixel_data(alpha),
        strict=True,
    ):
        if alpha_value < editable_alpha_threshold:
            editable_pixel_count += 1
            continue

        protected_pixel_count += 1
        delta = max(abs(int(left) - int(right)) for left, right in zip(base_pixel, candidate_pixel, strict=True))
        total_delta += delta
        max_delta = max(max_delta, delta)
        if delta > pixel_delta_threshold:
            changed_pixel_count += 1

    mean_delta = total_delta / protected_pixel_count if protected_pixel_count else 0.0
    changed_pixel_percent = changed_pixel_count / protected_pixel_count * 100 if protected_pixel_count else 0.0

    return OutsideMaskDrift(
        protected_pixel_count=protected_pixel_count,
        editable_pixel_count=editable_pixel_count,
        mean_delta=mean_delta,
        max_delta=max_delta,
        changed_pixel_count=changed_pixel_count,
        changed_pixel_percent=changed_pixel_percent,
        pixel_delta_threshold=pixel_delta_threshold,
    )


def evaluate_generated_image_preservation(
    *,
    source_image_path: Path,
    candidate_image_bytes: bytes,
    mask_image_path: Path,
    thresholds: PreservationThresholds | None = None,
) -> PreservationCheckResult:
    """Check whether a generated user-photo result preserved protected pixels.

    Same-aspect full-frame provider outputs may be normalized to the original
    dimensions before comparison. Different-aspect, tiny, crop-like, and patch
    outputs fail closed before drift metrics.
    """

    active_thresholds = thresholds or PreservationThresholds()
    metadata = PreservationImageMetadata(
        original_size=None,
        mask_size=None,
        provider_output_size=None,
        normalized_output_size=None,
        aspect_ratio_delta=None,
        size_normalized=False,
    )
    try:
        base_image = _load_image_copy(source_image_path)
        candidate_image = _load_candidate_bytes(candidate_image_bytes)
        mask_image = _load_image_copy(mask_image_path)
    except (OSError, SyntaxError, UnidentifiedImageError, ValueError):
        return PreservationCheckResult(
            passes=False,
            reason="invalid_preservation_inputs",
            message=PRESERVATION_FAILURE_MESSAGE,
            thresholds=active_thresholds,
            drift=None,
            metadata=metadata,
        )

    aspect_ratio_delta = abs(_aspect_ratio(base_image.size) - _aspect_ratio(candidate_image.size))
    metadata = PreservationImageMetadata(
        original_size=base_image.size,
        mask_size=mask_image.size,
        provider_output_size=candidate_image.size,
        normalized_output_size=candidate_image.size,
        aspect_ratio_delta=aspect_ratio_delta,
        size_normalized=False,
    )

    if base_image.size != mask_image.size:
        return PreservationCheckResult(
            passes=False,
            reason="size_mismatch",
            message=PRESERVATION_FAILURE_MESSAGE,
            thresholds=active_thresholds,
            drift=None,
            metadata=PreservationImageMetadata(
                original_size=base_image.size,
                mask_size=mask_image.size,
                provider_output_size=candidate_image.size,
                normalized_output_size=candidate_image.size,
                aspect_ratio_delta=aspect_ratio_delta,
                size_normalized=False,
                reject_reason="mask_size_mismatch",
            ),
        )

    normalized_candidate_bytes: bytes | None = None
    if candidate_image.size != base_image.size:
        if not _can_normalize_full_frame_candidate(
            original_size=base_image.size,
            candidate_size=candidate_image.size,
            aspect_ratio_delta=aspect_ratio_delta,
        ):
            return PreservationCheckResult(
                passes=False,
                reason="size_mismatch",
                message=PRESERVATION_FAILURE_MESSAGE,
                thresholds=active_thresholds,
                drift=None,
                metadata=PreservationImageMetadata(
                    original_size=base_image.size,
                    mask_size=mask_image.size,
                    provider_output_size=candidate_image.size,
                    normalized_output_size=candidate_image.size,
                    aspect_ratio_delta=aspect_ratio_delta,
                    size_normalized=False,
                    reject_reason="provider_output_not_full_frame_same_aspect",
                ),
            )
        # Use nearest-neighbor for the guardrail normalization so resizing does
        # not blur editable clothing pixels into protected regions and create
        # false protected-region drift at mask boundaries.
        candidate_image = candidate_image.convert("RGB").resize(base_image.size, Image.Resampling.NEAREST)
        normalized_candidate_bytes = _image_to_png_bytes(candidate_image)
        metadata = PreservationImageMetadata(
            original_size=base_image.size,
            mask_size=mask_image.size,
            provider_output_size=metadata.provider_output_size,
            normalized_output_size=candidate_image.size,
            aspect_ratio_delta=aspect_ratio_delta,
            size_normalized=True,
        )

    if _looks_like_rectangular_overlay(
        base_image,
        candidate_image,
        mask_image,
        pixel_delta_threshold=active_thresholds.pixel_delta_threshold,
    ):
        return PreservationCheckResult(
            passes=False,
            reason="rectangular_overlay_detected",
            message=PRESERVATION_FAILURE_MESSAGE,
            thresholds=active_thresholds,
            drift=None,
            metadata=PreservationImageMetadata(
                original_size=metadata.original_size,
                mask_size=metadata.mask_size,
                provider_output_size=metadata.provider_output_size,
                normalized_output_size=metadata.normalized_output_size,
                aspect_ratio_delta=metadata.aspect_ratio_delta,
                size_normalized=metadata.size_normalized,
                reject_reason="rectangular_overlay_detected",
            ),
            normalized_candidate_image_bytes=normalized_candidate_bytes,
        )

    try:
        drift = calculate_outside_mask_drift(
            base_image,
            candidate_image,
            mask_image,
            pixel_delta_threshold=active_thresholds.pixel_delta_threshold,
        )
    except ValueError:
        return PreservationCheckResult(
            passes=False,
            reason="invalid_preservation_inputs",
            message=PRESERVATION_FAILURE_MESSAGE,
            thresholds=active_thresholds,
            drift=None,
            metadata=PreservationImageMetadata(
                original_size=metadata.original_size,
                mask_size=metadata.mask_size,
                provider_output_size=metadata.provider_output_size,
                normalized_output_size=metadata.normalized_output_size,
                aspect_ratio_delta=metadata.aspect_ratio_delta,
                size_normalized=metadata.size_normalized,
                reject_reason="invalid_preservation_inputs",
            ),
        )

    if drift.editable_pixel_count <= 0:
        return PreservationCheckResult(
            passes=False,
            reason="empty_editable_mask_region",
            message=PRESERVATION_FAILURE_MESSAGE,
            thresholds=active_thresholds,
            drift=drift,
            metadata=PreservationImageMetadata(
                original_size=metadata.original_size,
                mask_size=metadata.mask_size,
                provider_output_size=metadata.provider_output_size,
                normalized_output_size=metadata.normalized_output_size,
                aspect_ratio_delta=metadata.aspect_ratio_delta,
                size_normalized=metadata.size_normalized,
                reject_reason="empty_editable_mask_region",
            ),
            normalized_candidate_image_bytes=normalized_candidate_bytes,
        )
    if drift.protected_pixel_count <= 0:
        return PreservationCheckResult(
            passes=False,
            reason="empty_protected_mask_region",
            message=PRESERVATION_FAILURE_MESSAGE,
            thresholds=active_thresholds,
            drift=drift,
            metadata=PreservationImageMetadata(
                original_size=metadata.original_size,
                mask_size=metadata.mask_size,
                provider_output_size=metadata.provider_output_size,
                normalized_output_size=metadata.normalized_output_size,
                aspect_ratio_delta=metadata.aspect_ratio_delta,
                size_normalized=metadata.size_normalized,
                reject_reason="empty_protected_mask_region",
            ),
            normalized_candidate_image_bytes=normalized_candidate_bytes,
        )
    if not drift.passes(
        max_mean_delta=active_thresholds.max_mean_delta,
        max_changed_pixel_percent=active_thresholds.max_changed_pixel_percent,
    ):
        return PreservationCheckResult(
            passes=False,
            reason="protected_region_drift",
            message=PRESERVATION_FAILURE_MESSAGE,
            thresholds=active_thresholds,
            drift=drift,
            metadata=PreservationImageMetadata(
                original_size=metadata.original_size,
                mask_size=metadata.mask_size,
                provider_output_size=metadata.provider_output_size,
                normalized_output_size=metadata.normalized_output_size,
                aspect_ratio_delta=metadata.aspect_ratio_delta,
                size_normalized=metadata.size_normalized,
                reject_reason="protected_region_drift",
            ),
            normalized_candidate_image_bytes=normalized_candidate_bytes,
        )

    return PreservationCheckResult(
        passes=True,
        reason=None,
        message="Generated image preserved protected regions outside the clothing mask.",
        thresholds=active_thresholds,
        drift=drift,
        metadata=metadata,
        normalized_candidate_image_bytes=normalized_candidate_bytes,
    )
