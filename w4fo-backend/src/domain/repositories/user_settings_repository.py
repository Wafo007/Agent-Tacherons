"""Interface (Port) : UserSettingsRepository."""

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from src.domain.entities.user_settings import UserSettings


class UserSettingsRepository(ABC):
    @abstractmethod
    async def get_by_user_id(self, user_id: UUID) -> Optional[UserSettings]:
        raise NotImplementedError

    @abstractmethod
    async def upsert(self, settings: UserSettings) -> UserSettings:
        raise NotImplementedError

    @abstractmethod
    async def list_all(self) -> List[UserSettings]:
        """Liste tous les paramètres utilisateurs — utilisé par le scheduler pour le réveil intelligent."""
        raise NotImplementedError
