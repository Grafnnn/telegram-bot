"""Generation schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import ORMModel

GENERATION_STATUS_PENDING = "pending"
GENERATION_STATUS_PROCESSING = "processing"
GENERATION_STATUS_COMPLETED = "completed"
GENERATION_STATUS_FAILED = "failed"
GENERATION_STATUSES = frozenset(
    {
        GENERATION_STATUS_PENDING,
        GENERATION_STATUS_PROCESSING,
        GENERATION_STATUS_COMPLETED,
        GENERATION_STATUS_FAILED,
    }
)
GenerationStatus = Literal["pending", "processing", "completed", "failed"]


class CatalogStyleGenerationRequest(BaseModel):
    telegram_id: int


class GenerationFabricRead(ORMModel):
    id: UUID
    sku: str
    name: str
    category: str


class GenerationGarmentStyleRead(ORMModel):
    id: UUID
    name: str
    category: str


class GenerationTelegramUserRead(ORMModel):
    id: UUID
    telegram_id: int
    username: str | None = None


class GenerationRead(ORMModel):
    id: UUID
    telegram_user_id: UUID | None = None
    fabric_id: UUID | None = None
    garment_style_id: UUID | None = None
    user_photo_url: str | None = None
    mask_image_url: str | None = None
    result_image_url: str | None = None
    mode: str
    prompt: str | None = None
    status: GenerationStatus
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    fabric: GenerationFabricRead | None = None
    garment_style: GenerationGarmentStyleRead | None = None
    telegram_user: GenerationTelegramUserRead | None = None
