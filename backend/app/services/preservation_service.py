"""Helpers for measuring user-photo preservation outside an edit mask.

The user-photo mask convention matches OpenAI image edit masks used elsewhere
in the backend: transparent pixels are editable, and opaque pixels are expected
protected. These helpers are intentionally local/deterministic and do not call
providers or inspect secrets.
"""

from __future__ import annotations

from dataclasses import dataclass
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


def _load_image_copy(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return image.copy()


def _load_candidate_bytes(candidate_image_bytes: bytes) -> Image.Image:
    if not candidate_image_bytes:
        raise ValueError("Generated image is empty.")
    with Image.open(BytesIO(candidate_image_bytes)) as image:
        return image.copy()


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

    This function intentionally fails on dimension mismatch instead of resizing
    provider output. A resized comparison could hide alignment bugs at mask
    boundaries, which is unsafe for user-photo try-on rollout decisions.
    """

    active_thresholds = thresholds or PreservationThresholds()
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
        )

    if len({base_image.size, candidate_image.size, mask_image.size}) != 1:
        return PreservationCheckResult(
            passes=False,
            reason="size_mismatch",
            message=PRESERVATION_FAILURE_MESSAGE,
            thresholds=active_thresholds,
            drift=None,
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
        )

    if drift.editable_pixel_count <= 0:
        return PreservationCheckResult(
            passes=False,
            reason="empty_editable_mask_region",
            message=PRESERVATION_FAILURE_MESSAGE,
            thresholds=active_thresholds,
            drift=drift,
        )
    if drift.protected_pixel_count <= 0:
        return PreservationCheckResult(
            passes=False,
            reason="empty_protected_mask_region",
            message=PRESERVATION_FAILURE_MESSAGE,
            thresholds=active_thresholds,
            drift=drift,
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
        )

    return PreservationCheckResult(
        passes=True,
        reason=None,
        message="Generated image preserved protected regions outside the clothing mask.",
        thresholds=active_thresholds,
        drift=drift,
    )
