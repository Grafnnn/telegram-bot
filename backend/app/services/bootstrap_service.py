"""Database and filesystem bootstrap helpers."""

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import Settings
from app.services.seed_service import seed_demo_data, seed_initial_admin
from app.utils.redaction import safe_exception_summary

logger = logging.getLogger(__name__)
UPLOAD_FOLDERS = ("fabrics", "garment-styles", "generations", "user-photos", "user-garment-crops", "user-photo-masks")


def prepare_upload_dirs(upload_dir: Path) -> None:
    """Create upload folders needed by storage helpers."""

    upload_dir.mkdir(parents=True, exist_ok=True)
    for folder in UPLOAD_FOLDERS:
        (upload_dir / folder).mkdir(parents=True, exist_ok=True)


def bootstrap_database(db: Session, settings: Settings) -> None:
    """Validate bootstrap settings, then seed required records idempotently."""

    settings.validate_bootstrap_config()
    try:
        seed_initial_admin(db, settings.initial_admin_email, settings.initial_admin_password)
        if settings.seed_demo_data:
            seed_demo_data(db)
    except Exception as exc:
        db.rollback()
        logger.error("Database bootstrap failed error=%s", safe_exception_summary(exc))
        raise
