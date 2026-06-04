"""Telegram user model."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TelegramUser(Base):
    __tablename__ = "telegram_users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String)
    first_name: Mapped[str | None] = mapped_column(String)
    last_name: Mapped[str | None] = mapped_column(String)
    selected_fabric_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("fabrics.id", ondelete="SET NULL"))
    selected_garment_style_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("garment_styles.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    generations = relationship("Generation", back_populates="telegram_user")
