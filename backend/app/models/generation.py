"""Generation model."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Generation(Base):
    __tablename__ = "generations"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    telegram_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("telegram_users.id", ondelete="SET NULL"), index=True)
    fabric_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("fabrics.id", ondelete="SET NULL"), index=True)
    garment_style_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("garment_styles.id", ondelete="SET NULL"), index=True)
    user_photo_url: Mapped[str | None] = mapped_column(Text)
    result_image_url: Mapped[str | None] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String, nullable=False)
    prompt: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending", server_default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    telegram_user = relationship("TelegramUser", back_populates="generations")
    fabric = relationship("Fabric", back_populates="generations")
    garment_style = relationship("GarmentStyle", back_populates="generations")
