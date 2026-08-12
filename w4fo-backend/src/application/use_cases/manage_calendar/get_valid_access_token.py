"""
Service applicatif : garantit qu'un access token Google valide est disponible,
en le rafraîchissant automatiquement si expiré.

Ce service est utilisé par tous les use cases du module Agenda avant d'appeler
`CalendarProvider`, pour éviter de dupliquer la logique de rafraîchissement.
"""

from uuid import UUID

from src.core.exceptions import EntityNotFoundError
from src.domain.repositories.google_oauth_token_repository import GoogleOAuthTokenRepository
from src.infrastructure.external_apis.google_oauth_client import compute_expiry, refresh_access_token


class GetValidGoogleAccessTokenUseCase:
    def __init__(self, token_repository: GoogleOAuthTokenRepository) -> None:
        self._token_repository = token_repository

    async def execute(self, user_id: UUID) -> str:
        token = await self._token_repository.get_by_user_id(user_id)
        if token is None:
            raise EntityNotFoundError(
                "Aucun compte Google connecté pour cet utilisateur. Merci de connecter Google Calendar."
            )

        if not token.is_expired():
            return token.access_token

        refreshed = await refresh_access_token(token.refresh_token)
        token.refresh(
            new_access_token=refreshed["access_token"],
            new_expires_at=compute_expiry(refreshed.get("expires_in", 3600)),
        )
        await self._token_repository.upsert(token)
        return token.access_token
