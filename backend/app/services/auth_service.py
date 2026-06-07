"""Admin auth service."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Admin
from app.utils.security import create_access_token, hash_password, verify_password


def authenticate_admin(db: Session, email: str, password: str) -> Admin | None:
    admin = db.scalar(select(Admin).where(Admin.email == email, Admin.is_active.is_(True)))
    if admin is None or not verify_password(password, admin.password_hash):
        return None
    return admin


def create_admin_token(admin: Admin) -> str:
    return create_access_token(str(admin.id))


def ensure_initial_admin(db: Session, email: str, password: str) -> Admin:
    admin = db.scalar(select(Admin).where(Admin.email == email))
    if admin:
        return admin
    admin = Admin(email=email, password_hash=hash_password(password), full_name="Initial Admin")
    db.add(admin)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing_admin = db.scalar(select(Admin).where(Admin.email == email))
        if existing_admin:
            return existing_admin
        raise
    db.refresh(admin)
    return admin
