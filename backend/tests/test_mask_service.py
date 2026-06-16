"""User-photo edit mask validation tests."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException
from PIL import Image, ImageDraw

from app.config import get_settings
from app.services.mask_service import (
    calculate_edit_coverage,
    ensure_mask_matches_base,
    save_mask_image,
    validate_edit_mask,
)
from app.services.storage_service import resolve_upload_path


@pytest.fixture()
def upload_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    get_settings.cache_clear()
    (tmp_path / "user-photo-masks").mkdir(parents=True)
    (tmp_path / "user-photos").mkdir(parents=True)
    yield tmp_path
    get_settings.cache_clear()


def _write_base(upload_root: Path, name: str = "photo.png", size: tuple[int, int] = (300, 300)) -> Path:
    path = upload_root / "user-photos" / name
    Image.new("RGB", size, color=(40, 120, 190)).save(path, format="PNG")
    return path


def _write_mask(
    upload_root: Path,
    name: str = "mask.png",
    size: tuple[int, int] = (300, 300),
    *,
    box: tuple[int, int, int, int] | None = (75, 75, 225, 225),
    mode: str = "RGBA",
) -> Path:
    path = upload_root / "user-photo-masks" / name
    if mode == "RGB":
        Image.new("RGB", size, color=(0, 0, 0)).save(path, format="PNG")
        return path
    mask = Image.new("RGBA", size, color=(0, 0, 0, 255))
    if box is not None:
        ImageDraw.Draw(mask).rectangle(box, fill=(0, 0, 0, 0))
    mask.save(path, format="PNG")
    return path


def _mask_bytes(size: tuple[int, int] = (300, 300), box: tuple[int, int, int, int] = (75, 75, 225, 225)) -> bytes:
    mask = Image.new("RGBA", size, color=(0, 0, 0, 255))
    ImageDraw.Draw(mask).rectangle(box, fill=(0, 0, 0, 0))
    buffer = BytesIO()
    mask.save(buffer, format="PNG")
    return buffer.getvalue()


def test_valid_rgba_png_mask_matching_base_passes(upload_root: Path) -> None:
    base = _write_base(upload_root)
    mask = _write_mask(upload_root)

    readiness = validate_edit_mask(mask, base)

    assert readiness.ready is True
    assert readiness.width == 300
    assert readiness.height == 300
    assert readiness.coverage_percent is not None
    assert 3 < readiness.coverage_percent < 80
    assert calculate_edit_coverage(mask) == pytest.approx(readiness.coverage_percent)


def test_mask_with_different_size_fails(upload_root: Path) -> None:
    base = _write_base(upload_root)
    mask = _write_mask(upload_root, size=(200, 300))

    readiness = validate_edit_mask(mask, base)

    assert readiness.ready is False
    assert readiness.error_code == "size_mismatch"
    assert str(upload_root) not in (readiness.error_message or "")


def test_mask_without_alpha_fails_controlled(upload_root: Path) -> None:
    base = _write_base(upload_root)
    mask = _write_mask(upload_root, mode="RGB")

    readiness = validate_edit_mask(mask, base)

    assert readiness.ready is False
    assert readiness.error_code == "missing_alpha"


def test_empty_mask_fails(upload_root: Path) -> None:
    base = _write_base(upload_root)
    mask = _write_mask(upload_root, box=None)

    readiness = validate_edit_mask(mask, base)

    assert readiness.ready is False
    assert readiness.error_code == "empty_mask"


def test_full_image_mask_fails_by_max_coverage(upload_root: Path) -> None:
    base = _write_base(upload_root)
    mask = _write_mask(upload_root, box=(0, 0, 300, 300))

    readiness = validate_edit_mask(mask, base)

    assert readiness.ready is False
    assert readiness.error_code == "full_image_mask"


def test_tiny_coverage_mask_fails(upload_root: Path) -> None:
    base = _write_base(upload_root)
    mask = _write_mask(upload_root, box=(10, 10, 11, 11))

    readiness = validate_edit_mask(mask, base)

    assert readiness.ready is False
    assert readiness.error_code == "tiny_coverage"


def test_broken_mask_bytes_fail_controlled(upload_root: Path) -> None:
    base = _write_base(upload_root)
    mask = upload_root / "user-photo-masks" / "broken.png"
    mask.write_bytes(b"\x89PNG\r\n\x1a\nnot-a-real-png")

    readiness = validate_edit_mask(mask, base)

    assert readiness.ready is False
    assert readiness.error_code == "unreadable_image"


def test_path_traversal_mask_path_is_rejected(upload_root: Path) -> None:
    base = _write_base(upload_root)

    readiness = validate_edit_mask(upload_root / ".." / "secret.png", base)

    assert readiness.ready is False
    assert readiness.error_code == "path_traversal"
    assert str(upload_root) not in (readiness.error_message or "")


def test_save_mask_image_persists_normalized_upload_url(upload_root: Path) -> None:
    mask_url = save_mask_image(_mask_bytes())
    mask_path = resolve_upload_path(mask_url)

    assert mask_url.startswith("/uploads/user-photo-masks/")
    assert mask_path.exists()
    assert mask_path.suffix == ".png"
    with Image.open(mask_path) as saved:
        assert saved.mode == "RGBA"


def test_ensure_mask_matches_base_raises_controlled_error(upload_root: Path) -> None:
    base = _write_base(upload_root)
    mask = _write_mask(upload_root, size=(100, 100))

    with pytest.raises(HTTPException) as exc_info:
        ensure_mask_matches_base(mask, base)

    assert exc_info.value.status_code == 400
    assert "valid" in str(exc_info.value.detail)
