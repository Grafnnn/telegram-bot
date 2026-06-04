"""File storage service for uploaded and generated images."""

from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.config import get_settings

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_FOLDERS = {"fabrics", "garment-styles", "generations", "user-photos"}


def _safe_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Разрешены только jpg, jpeg, png и webp файлы.")
    return ext


def resolve_upload_path(image_url: str) -> Path:
    """Resolve a public /uploads URL to a safe path inside UPLOAD_DIR."""

    if not image_url.startswith("/uploads/"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Можно использовать только URL из /uploads/.")
    relative = image_url.removeprefix("/uploads/")
    upload_root = get_settings().upload_dir.resolve()
    target = (upload_root / relative).resolve()
    if upload_root != target and upload_root not in target.parents:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Недопустимый путь к файлу.")
    if not target.exists() or not target.is_file():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Файл загрузки не найден.")
    return target


async def save_upload(file: UploadFile, folder: str) -> str:
    if folder not in ALLOWED_FOLDERS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Недопустимая папка загрузки.")
    settings = get_settings()
    ext = _safe_extension(file.filename or "upload")
    content = await file.read()
    max_size = settings.max_upload_size_bytes
    if len(content) > max_size:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Файл больше {settings.max_upload_size_mb} МБ.")
    target_dir = settings.upload_dir / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}.{ext}"
    (target_dir / filename).write_bytes(content)
    return f"/uploads/{folder}/{filename}"


def save_generated_image(content: bytes, extension: str = "png") -> str:
    """Persist generated image bytes and return a public /uploads URL."""

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Недопустимое расширение результата генерации.")
    target_dir = get_settings().upload_dir / "generations"
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}.{extension}"
    (target_dir / filename).write_bytes(content)
    return f"/uploads/generations/{filename}"
