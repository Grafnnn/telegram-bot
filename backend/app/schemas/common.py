"""Common API schemas."""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

DEFAULT_PAGE = 1
DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100


class HealthResponse(BaseModel):
    status: str = "ok"


class MessageResponse(BaseModel):
    message: str


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = Field(ge=DEFAULT_PAGE)
    limit: int = Field(ge=1, le=MAX_PAGE_LIMIT)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
