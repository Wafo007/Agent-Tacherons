"""Interface (Port) : CalendarEventRepository. Contrat de persistance locale des événements."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from src.domain.entities.calendar_event import CalendarEvent


class CalendarEventRepository(ABC):
    """Contrat de persistance pour l'entité CalendarEvent (cache local des événements)."""

    @abstractmethod
    async def create(self, event: CalendarEvent) -> CalendarEvent:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, event_id: UUID) -> Optional[CalendarEvent]:
        raise NotImplementedError

    @abstractmethod
    async def list_by_user(
        self,
        user_id: UUID,
        start_range: Optional[datetime] = None,
        end_range: Optional[datetime] = None,
    ) -> List[CalendarEvent]:
        """Liste les événements d'un utilisateur, optionnellement bornés à une plage temporelle."""
        raise NotImplementedError

    @abstractmethod
    async def update(self, event: CalendarEvent) -> CalendarEvent:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, event_id: UUID) -> None:
        raise NotImplementedError
