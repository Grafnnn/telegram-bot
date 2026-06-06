"""Garment style schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


GarmentStyleStatus = Literal["draft", "published", "hidden", "archived"]


class GarmentStyleBase(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    compatible_fabric_categories: list[str] | None = None
    status: GarmentStyleStatus = "draft"
    base_image_url: str | None = None
    mask_image_url: str | None = None

    @field_validator("name", "category", "description", "base_image_url", "mask_image_url", mode="before")
    @classmethod
    def strip_string(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("compatible_fabric_categories", mode="before")
    @classmethod
    def strip_string_list(cls, value):
        if isinstance(value, list):
            return [item.strip() if isinstance(item, str) else item for item in value]
        return value


class GarmentStyleCreate(GarmentStyleBase):
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=120)


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
