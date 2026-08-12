"""Interface (Port) : GoogleOAuthTokenRepository."""

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from src.domain.entities.google_oauth_token import GoogleOAuthToken


class GoogleOAuthTokenRepository(ABC):
    """Contrat de persistance pour les tokens OAuth Google d'un utilisateur."""

    @abstractmethod
    async def upsert(self, token: GoogleOAuthToken) -> GoogleOAuthToken:
        """Crée ou met à jour le token OAuth d'un utilisateur (un seul enregistrement par user_id)."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_user_id(self, user_id: UUID) -> Optional[GoogleOAuthToken]:
        raise NotImplementedError

    @abstractmethod
    async def delete_by_user_id(self, user_id: UUID) -> None:
        raise NotImplementedError
