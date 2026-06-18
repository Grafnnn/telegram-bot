"""Helpers for measuring user-photo preservation outside an edit mask.

The user-photo mask convention matches OpenAI image edit masks used elsewhere
in the backend: transparent pixels are editable, and opaque pixels are expected
protected. These helpers are intentionally local/deterministic and do not call
providers or inspect secrets.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

EDITABLE_ALPHA_THRESHOLD = 128
DEFAULT_PIXEL_DELTA_THRESHOLD = 8


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
