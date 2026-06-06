"""Generation routes."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import verify_bot_internal_token
from app.config import MissingOpenAIKeyError, get_settings
from app.database import get_db
from app.models import Fabric, GarmentStyle, Generation, TelegramUser
from app.schemas.generation import CatalogStyleGenerationRequest, GenerationRead
from app.services import image_generation_service
from app.services.image_generation_service import IMAGE_ERROR, IMAGE_EDIT_PROMPT
from app.services.storage_service import resolve_upload_path, save_generated_image, save_upload
from app.utils.redaction import safe_exception_summary

router = APIRouter(prefix="/generations", tags=["generations"])
logger = logging.getLogger(__name__)


def _generation_or_404(db: Session, generation_id: UUID) -> Generation:
    generation = db.get(Generation, generation_id)
    if generation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Генерация не найдена")
    return generation


def _telegram_user_or_404(db: Session, telegram_id: int) -> TelegramUser:
    user = db.scalar(select(TelegramUser).where(TelegramUser.telegram_id == telegram_id))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь Telegram не найден")
    return user


def _selected_published_fabric(db: Session, user: TelegramUser) -> Fabric:
    if user.selected_fabric_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Сначала выберите ткань.")
    fabric = db.scalar(select(Fabric).options(selectinload(Fabric.images)).where(Fabric.id == user.selected_fabric_id))
    if fabric is None or fabric.status != "published":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Выбранная ткань не найдена или больше не опубликована.")
    return fabric


def _selected_published_style(db: Session, user: TelegramUser) -> GarmentStyle:
    if user.selected_garment_style_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Сначала выберите фасон.")
    style = db.get(GarmentStyle, user.selected_garment_style_id)
    if style is None or style.status != "published":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Выбранный фасон не найдена или больше не опубликован.")
    return style


def _texture_image_url(fabric: Fabric) -> str:
    texture = next((image for image in fabric.images if image.image_type == "texture"), None)
    if texture is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "У выбранной ткани нет texture image.")
    return texture.image_url


def _base_image_url(style: GarmentStyle) -> str:
    if not style.base_image_url:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "У выбранного фасона нет base image.")
    return style.base_image_url


def _build_catalog_style_prompt(fabric: Fabric, style: GarmentStyle) -> str:
    details = [IMAGE_EDIT_PROMPT, f"Selected fabric id: {fabric.id}.", f"Selected garment style id: {style.id}."]
    if fabric.description_for_gpt:
        details.append(f"Fabric description: {fabric.description_for_gpt}")
    if style.description:
        details.append(f"Garment style description: {style.description}")
    return "\n".join(details)


def _safe_generation_error(exc: Exception) -> str:
    if isinstance(exc, MissingOpenAIKeyError):
        return str(exc)
    return IMAGE_ERROR


@router.post(
    "/catalog-style",
    response_model=GenerationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_bot_internal_token)],
)
def create_catalog_style_generation(payload: CatalogStyleGenerationRequest, db: Session = Depends(get_db)) -> Generation:
    user = _telegram_user_or_404(db, payload.telegram_id)
    fabric = _selected_published_fabric(db, user)
    style = _selected_published_style(db, user)
    texture_url = _texture_image_url(fabric)
    base_url = _base_image_url(style)
    texture_path = resolve_upload_path(texture_url)
    base_path = resolve_upload_path(base_url)
    mask_path = resolve_upload_path(style.mask_image_url) if style.mask_image_url else None
    prompt = _build_catalog_style_prompt(fabric, style)
    generation = Generation(
        telegram_user_id=user.id,
        fabric_id=fabric.id,
        garment_style_id=style.id,
        mode="catalog_style",
        prompt=prompt,
        status="processing",
    )
    db.add(generation)
    db.commit()
    db.refresh(generation)
    try:
        image_bytes = image_generation_service.generate_fabric_on_catalog_style(
            str(base_path),
            str(texture_path),
            str(mask_path) if mask_path else None,
            prompt,
        )
        generation.result_image_url = save_generated_image(image_bytes, "png")
        generation.status = "completed"
        generation.error_message = None
    except Exception as exc:
        generation.status = "failed"
        generation.error_message = _safe_generation_error(exc)
        logger.warning(
            "Catalog style generation failed generation_id=%s error=%s",
            generation.id,
            safe_exception_summary(exc),
        )
    db.commit()
    db.refresh(generation)
    return generation


@router.post(
    "/user-photo",
    response_model=GenerationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_bot_internal_token)],
)
async def create_user_photo_generation(telegram_user_id: UUID | None = Form(None), fabric_id: UUID = Form(...), photo: UploadFile = File(...), db: Session = Depends(get_db)) -> Generation:
    if db.get(Fabric, fabric_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ткань не найдена")
    photo_url = await save_upload(photo, "user-photos")
    configured = get_settings().is_openai_configured
    generation = Generation(telegram_user_id=telegram_user_id, fabric_id=fabric_id, user_photo_url=photo_url, mode="user_photo", status="pending" if configured else "failed", error_message=None if configured else IMAGE_ERROR)
    db.add(generation)
    db.commit()
    db.refresh(generation)
    return generation


@router.get("/{generation_id}", response_model=GenerationRead)
def get_generation(generation_id: UUID, db: Session = Depends(get_db)) -> Generation:
    return _generation_or_404(db, generation_id)
