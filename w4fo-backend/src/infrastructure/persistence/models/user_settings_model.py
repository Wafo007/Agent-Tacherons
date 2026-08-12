"""Modèle SQLAlchemy (table `user_settings`)."""

import uuid
from datetime import time

from sqlalchemy import Boolean, ForeignKey, Integer, String, Time
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.database import Base


class UserSettingsModel(Base):
    __tablename__ = "user_settings"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True
    )
    voice_id: Mapped[str] = mapped_column(String(50), default="default")
    volume_level: Mapped[int] = mapped_column(Integer, default=80)
    briefing_time: Mapped[time] = mapped_column(Time, default=time(hour=7, minute=30))
    dark_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    language: Mapped[str] = mapped_column(String(10), default="fr")
    autonomy_level: Mapped[str] = mapped_column(String(20), default="medium")
