"""Use case : mise à jour (report d'horaire) d'un événement d'agenda existant."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from src.application.use_cases.manage_calendar.get_valid_access_token import GetValidGoogleAccessTokenUseCase
from src.core.exceptions import EntityNotFoundError
from src.domain.entities.calendar_event import CalendarEvent
from src.domain.repositories.calendar_repository import CalendarEventRepository
from src.domain.repositories.google_oauth_token_repository import GoogleOAuthTokenRepository
from src.domain.services.calendar_provider import CalendarProvider


class UpdateCalendarEventUseCase:
    def __init__(
        self,
        calendar_repository: CalendarEventRepository,
        calendar_provider: CalendarProvider,
        token_repository: GoogleOAuthTokenRepository,
    ) -> None:
        self._calendar_repository = calendar_repository
        self._calendar_provider = calendar_provider
        self._token_repository = token_repository

    async def execute(
        self,
        event_id: UUID,
        new_start: Optional[datetime] = None,
        new_end: Optional[datetime] = None,
        new_title: Optional[str] = None,
    ) -> CalendarEvent:
        event = await self._calendar_repository.get_by_id(event_id)
        if event is None:
            raise EntityNotFoundError(f"Événement {event_id} introuvable.")

        if new_start is not None and new_end is not None:
            event.reschedule(new_start, new_end)
        if new_title is not None:
            event.title = new_title

        if event.google_event_id:
            try:
                token_use_case = GetValidGoogleAccessTokenUseCase(self._token_repository)
                access_token = await token_use_case.execute(event.user_id)
                await self._calendar_provider.update_event(
                    access_token=access_token,
                    google_event_id=event.google_event_id,
                    title=new_title,
                    start_time=new_start,
                    end_time=new_end,
                )
                event.synced = True
            except EntityNotFoundError:
                pass

        return await self._calendar_repository.update(event)
