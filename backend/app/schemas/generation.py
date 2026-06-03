"""Generation schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import ORMModel


class CatalogStyleGenerationRequest(BaseModel):
    telegram_user_id: UUID | None = None
    fabric_id: UUID
    garment_style_id: UUID


class GenerationRead(ORMModel):
    id: UUID
    telegram_user_id: UUID | None = None
    fabric_id: UUID | None = None
    garment_style_id: UUID | None = None
    user_photo_url: str | None = None
    result_image_url: str | None = None
    mode: str
    prompt: str | None = None
    status: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
