"""Fabric schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class FabricImageRead(ORMModel):
    id: UUID
    fabric_id: UUID
    image_url: str
    image_type: str
    sort_order: int
    created_at: datetime


class FabricBase(BaseModel):
    sku: str | None = None
    name: str | None = None
    category: str | None = None
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
    currency: str = "RUB"
    stock_status: str = "in_stock"
    stock_quantity: Decimal | None = None
    short_description: str | None = None
    full_description: str | None = None
    description_for_gpt: str | None = None
    tags: list[str] | None = None
    status: str = "draft"


class FabricCreate(FabricBase):
    sku: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)


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
    fabric: FabricRead
    score: int
    explanation: str
    matched_fields: list[str] = Field(default_factory=list)


class FabricRecommendResponse(BaseModel):
    preferences: dict
    items: list[FabricRecommendationItem]
    ai: dict
