"""FastAPI dependencies."""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

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
