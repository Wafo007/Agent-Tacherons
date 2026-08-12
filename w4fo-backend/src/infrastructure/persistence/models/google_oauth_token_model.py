"""
Modèle SQLAlchemy (table `google_oauth_tokens`).

Les colonnes `access_token`/`refresh_token` stockent des valeurs CHIFFRÉES
(chiffrement appliqué dans le repository, jamais de valeur en clair en base —
voir §11 du document d'architecture). La colonne `scopes` est stockée en texte
délimité par des virgules pour rester simple (pas besoin d'un type ARRAY dédié).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.database import Base


class GoogleOAuthTokenModel(Base):
    __tablename__ = "google_oauth_tokens"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True
    )
    encrypted_access_token: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scopes: Mapped[str] = mapped_column(String(1000), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
