from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FabricImageOut(BaseModel):
    id: str
    image_url: str
    is_main: bool
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class FabricOut(BaseModel):
    id: str
    name: str
    category: str | None = None
    color: str | None = None
    price: str | None = None
    availability: str | None = None
    short_description: str | None = None
    status: str
    images: list[FabricImageOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class RecommendationOut(BaseModel):
    fabric: FabricOut
    why: str
    possible_minus: str


class RecommendRequest(BaseModel):
    user_text: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=5)


class TelegramUserUpsert(BaseModel):
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class TelegramUserOut(BaseModel):
    id: str
    telegram_id: int
    selected_fabric_id: str | None = None
    selected_garment_style_id: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SelectFabricRequest(BaseModel):
    fabric_id: str


class SelectedFabricResponse(BaseModel):
    selected: bool
    message: str
    fabric: FabricOut | None = None
