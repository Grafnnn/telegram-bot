"""Generation routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Fabric, GarmentStyle, Generation
from app.schemas.generation import CatalogStyleGenerationRequest, GenerationRead
from app.services.image_generation_service import IMAGE_ERROR
from app.services.storage_service import save_upload

router = APIRouter(prefix="/generations", tags=["generations"])


def _generation_or_404(db: Session, generation_id: UUID) -> Generation:
    generation = db.get(Generation, generation_id)
    if generation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Генерация не найдена")
    return generation


@router.post("/catalog-style", response_model=GenerationRead, status_code=status.HTTP_201_CREATED)
def create_catalog_style_generation(payload: CatalogStyleGenerationRequest, db: Session = Depends(get_db)) -> Generation:
    if db.get(Fabric, payload.fabric_id) is None or db.get(GarmentStyle, payload.garment_style_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ткань или фасон не найдены")
    configured = get_settings().is_openai_configured
    generation = Generation(telegram_user_id=payload.telegram_user_id, fabric_id=payload.fabric_id, garment_style_id=payload.garment_style_id, mode="catalog_style", status="pending" if configured else "failed", error_message=None if configured else IMAGE_ERROR)
    db.add(generation)
    db.commit()
    db.refresh(generation)
    return generation


@router.post("/user-photo", response_model=GenerationRead, status_code=status.HTTP_201_CREATED)
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
