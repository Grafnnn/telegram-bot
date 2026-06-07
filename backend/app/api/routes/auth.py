"""Authentication routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.rate_limit import rate_limit_admin_login
from app.api.deps import get_current_admin
from app.database import get_db
from app.models import Admin
from app.schemas.auth import AdminRead, LoginRequest, TokenResponse
from app.services.auth_service import authenticate_admin, create_admin_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    _: None = Depends(rate_limit_admin_login),
    db: Session = Depends(get_db),
) -> TokenResponse:
    admin = authenticate_admin(db, payload.email, payload.password)
    if admin is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный email или пароль")
    return TokenResponse(access_token=create_admin_token(admin))


@router.get("/me", response_model=AdminRead)
def me(current_admin: Admin = Depends(get_current_admin)) -> Admin:
    return current_admin
