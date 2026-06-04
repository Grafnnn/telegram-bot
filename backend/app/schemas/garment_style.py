"""Garment style schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class GarmentStyleBase(BaseModel):
    name: str | None = None
    category: str | None = None
    description: str | None = None
    compatible_fabric_categories: list[str] | None = None
    status: str = "draft"
    base_image_url: str | None = None
    mask_image_url: str | None = None


class GarmentStyleCreate(GarmentStyleBase):
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)


class GarmentStyleUpdate(GarmentStyleBase):
    pass


class GarmentStyleRead(ORMModel):
    id: UUID
    name: str
    category: str
    description: str | None = None
    compatible_fabric_categories: list[str] | None = None
    status: str
    base_image_url: str | None = None
    mask_image_url: str | None = None
    created_at: datetime
    updated_at: datetime
