"""Fabric schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class FabricImageRead(ORMModel):
    id: UUID
    fabric_id: UUID
    image_url: str
    image_type: str
    sort_order: int
    created_at: datetime


FabricStatus = Literal["draft", "published", "hidden", "archived"]
StockStatus = Literal["in_stock", "preorder", "out_of_stock"]


class FabricBase(BaseModel):
    sku: str | None = Field(default=None, max_length=120)
    name: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=120)
    composition: str | None = Field(default=None, max_length=500)
    color: str | None = Field(default=None, max_length=120)
    shade: str | None = Field(default=None, max_length=120)
    pattern: str | None = Field(default=None, max_length=120)
    texture: str | None = Field(default=None, max_length=120)
    density: str | None = Field(default=None, max_length=120)
    stretch: str | None = Field(default=None, max_length=120)
    opacity: str | None = Field(default=None, max_length=120)
    shine: str | None = Field(default=None, max_length=120)
    season: list[str] | None = None
    recommended_for: list[str] | None = None
    not_recommended_for: list[str] | None = None
    price_per_meter: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="RUB", min_length=3, max_length=3)
    stock_status: StockStatus = "in_stock"
    stock_quantity: Decimal | None = Field(default=None, ge=0)
    short_description: str | None = Field(default=None, max_length=1000)
    full_description: str | None = None
    description_for_gpt: str | None = None
    tags: list[str] | None = None
    status: FabricStatus = "draft"

    @field_validator(
        "sku",
        "name",
        "category",
        "composition",
        "color",
        "shade",
        "pattern",
        "texture",
        "density",
        "stretch",
        "opacity",
        "shine",
        "currency",
        "short_description",
        "full_description",
        "description_for_gpt",
        mode="before",
    )
    @classmethod
    def strip_string(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("season", "recommended_for", "not_recommended_for", "tags", mode="before")
    @classmethod
    def strip_string_list(cls, value):
        if isinstance(value, list):
            return [item.strip() if isinstance(item, str) else item for item in value]
        return value


class FabricCreate(FabricBase):
    sku: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=120)


class FabricUpdate(FabricBase):
    pass


class FabricRead(ORMModel):
    id: UUID
    sku: str
    name: str
    category: str
    composition: str | None = None
    color: str | None = None
    shade: str | None = None
    pattern: str | None = None
    texture: str | None = None
    density: str | None = None
    stretch: str | None = None
    opacity: str | None = None
    shine: str | None = None
    season: list[str] | None = None
    recommended_for: list[str] | None = None
    not_recommended_for: list[str] | None = None
    price_per_meter: Decimal | None = None
    currency: str
    stock_status: str
    stock_quantity: Decimal | None = None
    short_description: str | None = None
    full_description: str | None = None
    description_for_gpt: str | None = None
    tags: list[str] | None = None
    status: str
    images: list[FabricImageRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class FabricAIRequest(BaseModel):
    fabric_data: dict
    image_url: str | None = None


class FabricRecommendRequest(BaseModel):
    user_text: str
    limit: int = 5


class FabricRecommendationItem(BaseModel):
    fabric_id: UUID
    score: float
    reason: str
    possible_issue: str | None = None
    fabric: FabricRead
    matched_fields: list[str] = Field(default_factory=list)


class FabricRecommendResponse(BaseModel):
    preferences: dict
    items: list[FabricRecommendationItem]
    ai: dict
