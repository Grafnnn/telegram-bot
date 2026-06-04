"""Authentication schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminRead(ORMModel):
    id: UUID
    email: EmailStr
    full_name: str | None = None
    role: str
    is_active: bool
    created_at: datetime
