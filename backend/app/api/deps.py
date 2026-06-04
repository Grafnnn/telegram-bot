"""FastAPI dependencies."""

from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Admin
from app.utils.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_admin(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Admin:
    subject = decode_access_token(token)
    if subject is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Недействительный токен")
    try:
        admin_id = UUID(subject)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Недействительный токен") from exc
    admin = db.get(Admin, admin_id)
    if admin is None or not admin.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Администратор не найден")
    return admin


def verify_bot_internal_token(x_bot_token: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.is_bot_internal_token_configured:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "BOT_INTERNAL_TOKEN is not configured for bot API access.",
        )
    if x_bot_token != settings.bot_internal_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Недействительный bot API token")
