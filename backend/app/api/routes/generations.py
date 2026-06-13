"""Generation routes."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.rate_limit import rate_limit_catalog_style_generation, rate_limit_user_photo_generation
from app.api.deps import verify_bot_internal_token
from app.config import MissingOpenAIKeyError
from app.database import get_db
from app.models import Fabric, GarmentStyle, Generation, TelegramUser
from app.schemas.generation import (
    GENERATION_STATUS_COMPLETED,
    GENERATION_STATUS_FAILED,
    GENERATION_STATUS_PENDING,
    GENERATION_STATUS_PROCESSING,
    CatalogStyleGenerationRequest,
    GenerationRead,
)
from app.services import image_generation_service
from app.services.image_generation_service import IMAGE_ERROR, IMAGE_EDIT_PROMPT, USER_PHOTO_EDIT_PROMPT
from app.services.storage_service import resolve_upload_path, save_generated_image, save_upload
from app.utils.redaction import safe_exception_summary

router = APIRouter(prefix="/generations", tags=["generations"])
logger = logging.getLogger(__name__)
ACTIVE_GENERATION_STATUSES = (GENERATION_STATUS_PENDING, GENERATION_STATUS_PROCESSING)


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


def _published_fabric_or_404(db: Session, fabric_id: UUID) -> Fabric:
    fabric = db.scalar(select(Fabric).options(selectinload(Fabric.images)).where(Fabric.id == fabric_id))
    if fabric is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ткань не найдена")
    if fabric.status != "published":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Выбранная ткань не найдена или больше не опубликована.")
    return fabric


def _selected_published_style(db: Session, user: TelegramUser) -> GarmentStyle:
    if user.selected_garment_style_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Сначала выберите фасон.")
    style = db.get(GarmentStyle, user.selected_garment_style_id)
    if style is None or style.status != "published":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Выбранный фасон не найден или больше не опубликован.")
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


def _build_user_photo_prompt(fabric: Fabric) -> str:
    details = [USER_PHOTO_EDIT_PROMPT, f"Selected fabric id: {fabric.id}."]
    if fabric.description_for_gpt:
        details.append(f"Fabric description: {fabric.description_for_gpt}")
    if fabric.category:
        details.append(f"Fabric category: {fabric.category}")
    if fabric.color:
        details.append(f"Fabric color: {fabric.color}")
    return "\n".join(details)


def _safe_generation_error(exc: Exception) -> str:
    if isinstance(exc, MissingOpenAIKeyError):
        return str(exc)
    return IMAGE_ERROR


def _active_catalog_style_generation(
    db: Session,
    user: TelegramUser,
    fabric: Fabric,
    style: GarmentStyle,
) -> Generation | None:
    return db.scalar(
        select(Generation)
        .where(
            Generation.telegram_user_id == user.id,
            Generation.fabric_id == fabric.id,
            Generation.garment_style_id == style.id,
            Generation.mode == "catalog_style",
            Generation.status.in_(ACTIVE_GENERATION_STATUSES),
        )
        .order_by(Generation.created_at.desc())
    )


def _mark_generation_completed(generation: Generation, image_bytes: bytes) -> None:
    generation.result_image_url = save_generated_image(image_bytes, "png")
    generation.status = GENERATION_STATUS_COMPLETED
    generation.error_message = None


def _mark_generation_failed(generation: Generation, exc: Exception) -> None:
    generation.status = GENERATION_STATUS_FAILED
    generation.error_message = _safe_generation_error(exc)


@router.post(
    "/catalog-style",
    response_model=GenerationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_bot_internal_token), Depends(rate_limit_catalog_style_generation)],
)
def create_catalog_style_generation(
    payload: CatalogStyleGenerationRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> Generation:
    user = _telegram_user_or_404(db, payload.telegram_id)
    fabric = _selected_published_fabric(db, user)
    style = _selected_published_style(db, user)
    active_generation = _active_catalog_style_generation(db, user, fabric, style)
    if active_generation is not None:
        response.status_code = status.HTTP_200_OK
        return active_generation
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
        status=GENERATION_STATUS_PROCESSING,
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
        _mark_generation_completed(generation, image_bytes)
    except Exception as exc:
        _mark_generation_failed(generation, exc)
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
    dependencies=[Depends(verify_bot_internal_token), Depends(rate_limit_user_photo_generation)],
)
async def create_user_photo_generation(
    telegram_id: int | None = Form(None),
    telegram_user_id: UUID | None = Form(None),
    fabric_id: UUID = Form(...),
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Generation:
    return await _create_user_photo_generation(telegram_id, telegram_user_id, fabric_id, photo, db)


async def _create_user_photo_generation(
    telegram_id: int | None,
    telegram_user_id: UUID | None,
    fabric_id: UUID,
    photo: UploadFile,
    db: Session,
) -> Generation:
    linked_user_id = telegram_user_id
    if telegram_id is not None:
        linked_user_id = _telegram_user_or_404(db, telegram_id).id
    fabric = _published_fabric_or_404(db, fabric_id)
    texture_url = _texture_image_url(fabric)
    texture_path = resolve_upload_path(texture_url)
    photo_url = await save_upload(photo, "user-photos")
    photo_path = resolve_upload_path(photo_url)
    prompt = _build_user_photo_prompt(fabric)
    generation = Generation(
        telegram_user_id=linked_user_id,
        fabric_id=fabric_id,
        user_photo_url=photo_url,
        mode="user_photo",
        prompt=prompt,
        status=GENERATION_STATUS_PROCESSING,
    )
    db.add(generation)
    db.commit()
    db.refresh(generation)
    try:
        image_bytes = image_generation_service.generate_fabric_on_user_photo(
            str(photo_path),
            str(texture_path),
            prompt,
        )
        _mark_generation_completed(generation, image_bytes)
    except Exception as exc:
        _mark_generation_failed(generation, exc)
        logger.warning(
            "User photo generation failed generation_id=%s error=%s",
            generation.id,
            safe_exception_summary(exc),
        )
    db.commit()
    db.refresh(generation)
    return generation


@router.get("/{generation_id}", response_model=GenerationRead)
def get_generation(generation_id: UUID, db: Session = Depends(get_db)) -> Generation:
    return _generation_or_404(db, generation_id)
