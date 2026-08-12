"""
Implémentation concrète (Adapter) de GoogleOAuthTokenRepository.

Chiffre les tokens avant écriture et les déchiffre à la lecture — conformément
au §11 du document d'architecture (jamais de token OAuth en clair en base).
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.encryption import decrypt, encrypt
from src.domain.entities.google_oauth_token import GoogleOAuthToken
from src.domain.repositories.google_oauth_token_repository import GoogleOAuthTokenRepository
from src.infrastructure.persistence.models.google_oauth_token_model import GoogleOAuthTokenModel


class SQLAlchemyGoogleOAuthTokenRepository(GoogleOAuthTokenRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(model: GoogleOAuthTokenModel) -> GoogleOAuthToken:
        return GoogleOAuthToken(
            id=model.id,
            user_id=model.user_id,
            access_token=decrypt(model.encrypted_access_token),
            refresh_token=decrypt(model.encrypted_refresh_token),
            expires_at=model.expires_at,
            scopes=model.scopes.split(",") if model.scopes else [],
            updated_at=model.updated_at,
        )

    async def upsert(self, token: GoogleOAuthToken) -> GoogleOAuthToken:
        result = await self._session.execute(
            select(GoogleOAuthTokenModel).where(GoogleOAuthTokenModel.user_id == token.user_id)
        )
        model = result.scalar_one_or_none()

        if model is None:
            model = GoogleOAuthTokenModel(id=token.id, user_id=token.user_id)
            self._session.add(model)

        model.encrypted_access_token = encrypt(token.access_token)
        model.encrypted_refresh_token = encrypt(token.refresh_token)
        model.expires_at = token.expires_at
        model.scopes = ",".join(token.scopes)

        await self._session.commit()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get_by_user_id(self, user_id: UUID) -> Optional[GoogleOAuthToken]:
        result = await self._session.execute(
            select(GoogleOAuthTokenModel).where(GoogleOAuthTokenModel.user_id == user_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def delete_by_user_id(self, user_id: UUID) -> None:
        result = await self._session.execute(
            select(GoogleOAuthTokenModel).where(GoogleOAuthTokenModel.user_id == user_id)
        )
        model = result.scalar_one_or_none()
        if model is not None:
            await self._session.delete(model)
            await self._session.commit()
