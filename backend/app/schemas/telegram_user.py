"""Telegram user schemas for bot-facing API."""

from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel
from app.schemas.fabric import FabricRead
from app.schemas.garment_style import GarmentStyleRead


class TelegramUserUpsert(BaseModel):
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class TelegramUserRead(ORMModel):
    id: UUID
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    selected_fabric_id: UUID | None = None
    selected_garment_style_id: UUID | None = None


class SelectedFabricUpdate(BaseModel):
    fabric_id: UUID = Field(description="Published fabric id selected by the Telegram user")


class SelectedGarmentStyleUpdate(BaseModel):
    garment_style_id: UUID = Field(description="Published garment style id selected by the Telegram user")


class SelectedFabricRead(BaseModel):
    fabric: FabricRead | None = None
    message: str


class SelectedGarmentStyleRead(BaseModel):
    garment_style: GarmentStyleRead | None = None
    message: str


class TelegramSelectionRead(BaseModel):
    fabric: FabricRead | None = None
    garment_style: GarmentStyleRead | None = None
    message: str
