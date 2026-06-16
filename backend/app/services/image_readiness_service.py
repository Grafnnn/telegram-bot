"""Readiness checks for uploaded fabric images."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError

from app.models import Fabric, FabricImage
from app.services.storage_service import ALLOWED_EXTENSIONS, ALLOWED_IMAGE_MIME_TYPES, UploadPathResolutionError, resolve_upload_path

MIN_AI_REFERENCE_DIMENSION = 256
AI_COMPATIBLE_IMAGE_MODES = {"RGB", "RGBA", "L", "LA", "P", "CMYK"}
FATAL_REFERENCE_URL_ERRORS = {"unsupported_prefix", "path_traversal"}
PUBLIC_CATALOG_REQUIRED_IMAGE_TYPES = ("main", "texture")

ERROR_MESSAGES = {
    "empty_image_url": "Image URL is empty.",
    "unsupported_prefix": "Image URL must point to /uploads/.",
    "path_traversal": "Image URL is unsafe.",
    "missing_file": "Image file is missing.",
    "empty_file": "Image file is empty.",
    "unsupported_extension": "Image extension is unsupported.",
    "unreadable_image": "Image file cannot be decoded.",
    "unsupported_mime": "Image MIME type is unsupported.",
    "unsupported_mode": "Image mode is unsupported.",
    "tiny_image": f"Image is smaller than {MIN_AI_REFERENCE_DIMENSION}x{MIN_AI_REFERENCE_DIMENSION}.",
}


@dataclass
class ImageFileReadiness:
    image_id: str | None
    image_type: str | None
    image_url: str | None
    file_exists: bool = False
    file_ready: bool = False
    ai_reference_ready: bool = False
    width: int | None = None
    height: int | None = None
    image_format: str | None = None
    image_mode: str | None = None
    mime_type: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    def mark_error(self, code: str) -> "ImageFileReadiness":
        self.error_code = code
        self.error_message = ERROR_MESSAGES.get(code, "Image is not ready.")
        return self

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "image_id": self.image_id,
            "image_type": self.image_type,
            "image_url": self.image_url,
            "file_exists": self.file_exists,
            "file_ready": self.file_ready,
            "ai_reference_ready": self.ai_reference_ready,
            "width": self.width,
            "height": self.height,
            "image_format": self.image_format,
            "image_mode": self.image_mode,
            "mime_type": self.mime_type,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


@dataclass
class MissingUploadFile:
    image_id: str | None
    image_type: str | None
    image_url: str | None
    error_code: str | None = None
    error_message: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "image_id": self.image_id,
            "image_type": self.image_type,
            "image_url": self.image_url,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


@dataclass
class FabricReadinessDiagnostics:
    public_catalog_ready: bool
    try_on_ready: bool
    missing_required_image_types: list[str] = field(default_factory=list)
    missing_upload_files: list[MissingUploadFile] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "public_catalog_ready": self.public_catalog_ready,
            "try_on_ready": self.try_on_ready,
            "missing_required_image_types": self.missing_required_image_types,
            "missing_upload_files": [item.to_public_dict() for item in self.missing_upload_files],
            "warnings": self.warnings,
        }


@dataclass
class FabricImageReadinessReport:
    has_main_image_record: bool
    has_texture_image_record: bool
    main_file_ready: bool
    texture_file_ready: bool
    public_catalog_ready: bool
    ai_reference_ready: bool
    try_on_ready: bool
    preferred_reference_type: str | None
    missing_required_image_types: list[str] = field(default_factory=list)
    missing_upload_files: list[MissingUploadFile] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    readiness_errors: list[str] = field(default_factory=list)
    images: list[ImageFileReadiness] = field(default_factory=list)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "has_main_image_record": self.has_main_image_record,
            "has_texture_image_record": self.has_texture_image_record,
            "main_file_ready": self.main_file_ready,
            "texture_file_ready": self.texture_file_ready,
            "public_catalog_ready": self.public_catalog_ready,
            "ai_reference_ready": self.ai_reference_ready,
            "try_on_ready": self.try_on_ready,
            "preferred_reference_type": self.preferred_reference_type,
            "missing_required_image_types": self.missing_required_image_types,
            "missing_upload_files": [item.to_public_dict() for item in self.missing_upload_files],
            "warnings": self.warnings,
            "readiness_errors": self.readiness_errors,
            "images": [image.to_public_dict() for image in self.images],
        }

    def to_diagnostics(self) -> FabricReadinessDiagnostics:
        return FabricReadinessDiagnostics(
            public_catalog_ready=self.public_catalog_ready,
            try_on_ready=self.try_on_ready,
            missing_required_image_types=self.missing_required_image_types,
            missing_upload_files=self.missing_upload_files,
            warnings=self.warnings,
        )

    def to_diagnostics_dict(self) -> dict[str, Any]:
        return self.to_diagnostics().to_public_dict()


def _image_sort_key(image: FabricImage) -> tuple[int, str]:
    return (image.sort_order, str(image.id))


def _image_identity(image: FabricImage | None, image_url: str | None = None, image_type: str | None = None) -> ImageFileReadiness:
    return ImageFileReadiness(
        image_id=str(image.id) if image is not None else None,
        image_type=image.image_type if image is not None else image_type,
        image_url=image.image_url if image is not None else image_url,
    )


def check_uploaded_image_readiness(
    image_url: str | None,
    *,
    image: FabricImage | None = None,
    image_type: str | None = None,
    min_dimension: int = MIN_AI_REFERENCE_DIMENSION,
) -> ImageFileReadiness:
    """Return sanitized readiness details for a public /uploads image URL."""

    readiness = _image_identity(image, image_url, image_type)
    if not readiness.image_url:
        return readiness.mark_error("empty_image_url")
    try:
        path = resolve_upload_path(readiness.image_url)
    except UploadPathResolutionError as exc:
        return readiness.mark_error(exc.reason)
    except HTTPException:
        return readiness.mark_error("missing_file")

    readiness.file_exists = True
    if path.stat().st_size <= 0:
        return readiness.mark_error("empty_file")
    if path.suffix.lower().lstrip(".") not in ALLOWED_EXTENSIONS:
        return readiness.mark_error("unsupported_extension")

    try:
        with Image.open(path) as image_file:
            image_file.verify()
        with Image.open(path) as image_file:
            readiness.width, readiness.height = image_file.size
            readiness.image_format = image_file.format
            readiness.image_mode = image_file.mode
            readiness.mime_type = Image.MIME.get(image_file.format or "")
    except (OSError, SyntaxError, UnidentifiedImageError) as exc:
        return readiness.mark_error("unreadable_image")

    if readiness.mime_type not in ALLOWED_IMAGE_MIME_TYPES:
        return readiness.mark_error("unsupported_mime")
    if readiness.image_mode not in AI_COMPATIBLE_IMAGE_MODES:
        return readiness.mark_error("unsupported_mode")

    readiness.file_ready = True
    if readiness.width is None or readiness.height is None or min(readiness.width, readiness.height) < min_dimension:
        return readiness.mark_error("tiny_image")

    readiness.ai_reference_ready = True
    return readiness


def _readiness_error_label(readiness: ImageFileReadiness) -> str:
    image_type = readiness.image_type or "image"
    code = readiness.error_code or "not_ready"
    return f"{image_type}:{code}"


def fabric_image_readiness_report_from_images(images_source: Iterable[FabricImage]) -> FabricImageReadinessReport:
    """Summarize file and AI reference readiness for fabric image records."""

    images = [check_uploaded_image_readiness(image.image_url, image=image) for image in sorted(images_source, key=_image_sort_key)]
    main_images = [image for image in images if image.image_type == "main"]
    texture_images = [image for image in images if image.image_type == "texture"]
    preferred_reference_type = None
    if any(image.ai_reference_ready for image in texture_images):
        preferred_reference_type = "texture"
    elif any(image.ai_reference_ready for image in main_images):
        preferred_reference_type = "main"
    has_required_image_record = {
        "main": bool(main_images),
        "texture": bool(texture_images),
    }
    required_file_ready = {
        "main": any(image.file_ready for image in main_images),
        "texture": any(image.file_ready for image in texture_images),
    }
    missing_required_image_types = [
        image_type
        for image_type in PUBLIC_CATALOG_REQUIRED_IMAGE_TYPES
        if not has_required_image_record[image_type]
    ]
    missing_upload_files = [
        MissingUploadFile(
            image_id=image.image_id,
            image_type=image.image_type,
            image_url=image.image_url,
            error_code=image.error_code,
            error_message=image.error_message,
        )
        for image in images
        if image.image_type in PUBLIC_CATALOG_REQUIRED_IMAGE_TYPES and not image.file_ready
    ]
    warnings = []
    if missing_required_image_types:
        warnings.append("Missing required image record: " + ", ".join(missing_required_image_types))
    if missing_upload_files:
        warnings.append(
            "Missing or unreadable required upload file: "
            + ", ".join(str(item.image_type or "image") for item in missing_upload_files)
        )
    public_catalog_ready = (
        not missing_required_image_types
        and not missing_upload_files
        and all(required_file_ready[image_type] for image_type in PUBLIC_CATALOG_REQUIRED_IMAGE_TYPES)
    )
    return FabricImageReadinessReport(
        has_main_image_record=bool(main_images),
        has_texture_image_record=bool(texture_images),
        main_file_ready=required_file_ready["main"],
        texture_file_ready=required_file_ready["texture"],
        public_catalog_ready=public_catalog_ready,
        ai_reference_ready=preferred_reference_type is not None,
        try_on_ready=preferred_reference_type is not None,
        preferred_reference_type=preferred_reference_type,
        missing_required_image_types=missing_required_image_types,
        missing_upload_files=missing_upload_files,
        warnings=warnings,
        readiness_errors=[_readiness_error_label(image) for image in images if not image.ai_reference_ready],
        images=images,
    )


def fabric_image_readiness_report(fabric: Fabric) -> FabricImageReadinessReport:
    """Summarize file and AI reference readiness for one fabric."""

    return fabric_image_readiness_report_from_images(fabric.images)


def fabric_readiness_diagnostics(fabric: Fabric) -> FabricReadinessDiagnostics:
    """Return compact sanitized readiness diagnostics for API responses."""

    return fabric_image_readiness_report(fabric).to_diagnostics()


def is_public_catalog_ready(fabric: Fabric) -> bool:
    """Return whether a fabric is safe to expose in the public catalog."""

    return fabric_image_readiness_report(fabric).public_catalog_ready


def _candidate_images(fabric: Fabric, image_type: str) -> list[FabricImage]:
    return sorted((image for image in fabric.images if image.image_type == image_type), key=_image_sort_key)


def select_ready_fabric_reference_path(fabric: Fabric) -> tuple[Path, str]:
    """Return the selected fabric's AI-ready reference path, preferring texture then main."""

    candidates = [
        *[(image, "texture") for image in _candidate_images(fabric, "texture")],
        *[(image, "main") for image in _candidate_images(fabric, "main")],
    ]
    if not candidates:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "У выбранной ткани нет изображения для примерки.")

    for image, image_type in candidates:
        readiness = check_uploaded_image_readiness(image.image_url, image=image)
        if readiness.ai_reference_ready:
            return resolve_upload_path(image.image_url), image_type
        if readiness.error_code in FATAL_REFERENCE_URL_ERRORS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Selected fabric reference image URL is invalid.")

    raise HTTPException(status.HTTP_400_BAD_REQUEST, "Selected fabric has no usable reference image.")
