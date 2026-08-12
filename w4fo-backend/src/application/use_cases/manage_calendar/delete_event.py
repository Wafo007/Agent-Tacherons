"""Use case : suppression d'un événement d'agenda, synchronisée avec Google Calendar."""

from uuid import UUID

from src.application.use_cases.manage_calendar.get_valid_access_token import GetValidGoogleAccessTokenUseCase
from src.core.exceptions import EntityNotFoundError
from src.domain.repositories.calendar_repository import CalendarEventRepository
from src.domain.repositories.google_oauth_token_repository import GoogleOAuthTokenRepository
from src.domain.services.calendar_provider import CalendarProvider


class DeleteCalendarEventUseCase:
    def __init__(
        self,
        calendar_repository: CalendarEventRepository,
        calendar_provider: CalendarProvider,
        token_repository: GoogleOAuthTokenRepository,
    ) -> None:
        self._calendar_repository = calendar_repository
        self._calendar_provider = calendar_provider
        self._token_repository = token_repository

    async def execute(self, event_id: UUID) -> None:
        event = await self._calendar_repository.get_by_id(event_id)
        if event is None:
            raise EntityNotFoundError(f"Événement {event_id} introuvable.")

        if event.synced and event.google_event_id:
            try:
                token_use_case = GetValidGoogleAccessTokenUseCase(self._token_repository)
                access_token = await token_use_case.execute(event.user_id)
                await self._calendar_provider.delete_event(access_token, event.google_event_id)
            except EntityNotFoundError:
                pass  # Compte Google déconnecté entre-temps : on supprime uniquement en local

        await self._calendar_repository.delete(event_id)
