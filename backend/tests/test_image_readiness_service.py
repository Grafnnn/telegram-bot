"""Fabric image readiness checks."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from PIL import Image

from app.config import get_settings
from app.services.image_readiness_service import (
    check_uploaded_image_readiness,
    fabric_image_readiness_report,
    select_ready_fabric_reference_path,
)


@pytest.fixture()
def upload_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    get_settings.cache_clear()
    (tmp_path / "fabrics").mkdir(parents=True)
    yield tmp_path
    get_settings.cache_clear()


def _write_png(upload_root: Path, image_url: str, size: tuple[int, int] = (300, 300), mode: str = "RGB") -> Path:
    path = upload_root / image_url.removeprefix("/uploads/")
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new(mode, size, color=(34, 120, 180))
    image.save(path, format="PNG")
    return path


def _image(image_url: str, image_type: str, sort_order: int = 0):
    return SimpleNamespace(id=uuid4(), image_url=image_url, image_type=image_type, sort_order=sort_order)


def _fabric(images):
    return SimpleNamespace(id=uuid4(), images=images)


def test_valid_png_image_is_ai_ready(upload_root: Path) -> None:
    image_url = "/uploads/fabrics/ready.png"
    _write_png(upload_root, image_url)

    readiness = check_uploaded_image_readiness(image_url, image_type="texture")

    assert readiness.file_exists is True
    assert readiness.file_ready is True
    assert readiness.ai_reference_ready is True
    assert readiness.width == 300
    assert readiness.height == 300
    assert readiness.mime_type == "image/png"
    assert readiness.error_code is None


def test_missing_file_returns_not_ready_without_server_path(upload_root: Path) -> None:
    readiness = check_uploaded_image_readiness("/uploads/fabrics/missing.png", image_type="main")

    assert readiness.file_exists is False
    assert readiness.file_ready is False
    assert readiness.ai_reference_ready is False
    assert readiness.error_code == "missing_file"
    assert str(upload_root) not in (readiness.error_message or "")


def test_tiny_placeholder_is_not_ai_reference_ready(upload_root: Path) -> None:
    image_url = "/uploads/fabrics/tiny.png"
    _write_png(upload_root, image_url, size=(1, 1))

    readiness = check_uploaded_image_readiness(image_url, image_type="texture")

    assert readiness.file_ready is True
    assert readiness.ai_reference_ready is False
    assert readiness.error_code == "tiny_image"


def test_unsupported_extension_is_rejected(upload_root: Path) -> None:
    image_url = "/uploads/fabrics/not-ready.gif"
    path = upload_root / "fabrics" / "not-ready.gif"
    path.write_bytes(b"GIF89a")

    readiness = check_uploaded_image_readiness(image_url, image_type="texture")

    assert readiness.file_exists is True
    assert readiness.file_ready is False
    assert readiness.error_code == "unsupported_extension"


def test_path_traversal_is_rejected(upload_root: Path) -> None:
    readiness = check_uploaded_image_readiness("/uploads/../secret.png", image_type="texture")

    assert readiness.file_ready is False
    assert readiness.ai_reference_ready is False
    assert readiness.error_code == "path_traversal"
    assert str(upload_root) not in (readiness.error_message or "")


def test_broken_image_bytes_are_rejected(upload_root: Path) -> None:
    image_url = "/uploads/fabrics/broken.png"
    path = upload_root / "fabrics" / "broken.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\nnot-a-real-png")

    readiness = check_uploaded_image_readiness(image_url, image_type="main")

    assert readiness.file_exists is True
    assert readiness.file_ready is False
    assert readiness.ai_reference_ready is False
    assert readiness.error_code == "unreadable_image"


def test_fabric_report_prefers_ready_texture_over_ready_main(upload_root: Path) -> None:
    main_url = "/uploads/fabrics/main.png"
    texture_url = "/uploads/fabrics/texture.png"
    _write_png(upload_root, main_url)
    _write_png(upload_root, texture_url)
    report = fabric_image_readiness_report(_fabric([_image(main_url, "main"), _image(texture_url, "texture")]))

    assert report.has_main_image_record is True
    assert report.has_texture_image_record is True
    assert report.main_file_ready is True
    assert report.texture_file_ready is True
    assert report.public_catalog_ready is True
    assert report.ai_reference_ready is True
    assert report.try_on_ready is True
    assert report.preferred_reference_type == "texture"


def test_fabric_report_requires_main_and_texture_files_for_public_catalog(upload_root: Path) -> None:
    main_url = "/uploads/fabrics/main-public.png"
    texture_url = "/uploads/fabrics/missing-texture.png"
    _write_png(upload_root, main_url)
    report = fabric_image_readiness_report(_fabric([_image(main_url, "main"), _image(texture_url, "texture")]))

    assert report.has_main_image_record is True
    assert report.has_texture_image_record is True
    assert report.main_file_ready is True
    assert report.texture_file_ready is False
    assert report.public_catalog_ready is False
    assert report.missing_required_image_types == []
    assert len(report.missing_upload_files) == 1
    assert report.missing_upload_files[0].image_type == "texture"
    assert report.missing_upload_files[0].error_code == "missing_file"
    public_payload = report.to_public_dict()
    assert str(upload_root) not in str(public_payload)


def test_broken_texture_falls_back_to_ready_same_fabric_main(upload_root: Path) -> None:
    main_url = "/uploads/fabrics/main-fallback.png"
    texture_url = "/uploads/fabrics/broken-texture.png"
    main_path = _write_png(upload_root, main_url)
    (upload_root / "fabrics" / "broken-texture.png").write_bytes(b"\x89PNG\r\n\x1a\nbroken")
    path, image_type = select_ready_fabric_reference_path(
        _fabric([_image(texture_url, "texture"), _image(main_url, "main")])
    )

    assert path == main_path
    assert image_type == "main"


def test_broken_texture_and_missing_main_fail_controlled(upload_root: Path) -> None:
    texture_url = "/uploads/fabrics/broken-texture.png"
    main_url = "/uploads/fabrics/missing-main.png"
    (upload_root / "fabrics" / "broken-texture.png").write_bytes(b"\x89PNG\r\n\x1a\nbroken")

    with pytest.raises(HTTPException) as exc_info:
        select_ready_fabric_reference_path(_fabric([_image(texture_url, "texture"), _image(main_url, "main")]))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Selected fabric has no usable reference image."
