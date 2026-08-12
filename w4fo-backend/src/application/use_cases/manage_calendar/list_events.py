"""Use case : lister les événements d'agenda d'un utilisateur sur une plage temporelle."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from src.domain.entities.calendar_event import CalendarEvent
from src.domain.repositories.calendar_repository import CalendarEventRepository


class ListCalendarEventsUseCase:
    """
    Lit les événements depuis le cache local (PostgreSQL), pas directement depuis
    Google Calendar, pour garantir une réponse rapide et disponible même hors ligne
    ou si Google Calendar est indisponible. La fraîcheur du cache est assurée par
    la synchronisation à l'écriture (create/update/delete) — une synchronisation
    périodique complète (webhooks Google Calendar push) est prévue en V2+.
    """

    def __init__(self, calendar_repository: CalendarEventRepository) -> None:
        self._calendar_repository = calendar_repository

    async def execute(
        self, user_id: UUID, start_range: Optional[datetime] = None, end_range: Optional[datetime] = None
    ) -> List[CalendarEvent]:
        return await self._calendar_repository.list_by_user(user_id, start_range=start_range, end_range=end_range)
