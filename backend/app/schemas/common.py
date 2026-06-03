"""Common API schemas."""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class HealthResponse(BaseModel):
    status: str = "ok"


class MessageResponse(BaseModel):
    message: str


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = Field(ge=1)
    limit: int = Field(ge=1)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
