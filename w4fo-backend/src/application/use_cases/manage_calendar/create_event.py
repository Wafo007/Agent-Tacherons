"""
Use case : création d'un événement d'agenda, avec détection de conflit
et synchronisation vers Google Calendar.

Applique la règle métier du document d'architecture ("il peut me prévenir
d'un conflit d'agenda") : la création n'est PAS bloquée en cas de chevauchement
(l'utilisateur peut vouloir un rendez-vous en double sciemment), mais les
conflits détectés sont retournés pour que l'agent puisse en informer
l'utilisateur ou déclencher une notification (§6 — Notifications intelligentes).
"""

from src.application.dto.calendar_dto import CreateEventDTO, CreateEventResultDTO
from src.application.use_cases.manage_calendar.get_valid_access_token import GetValidGoogleAccessTokenUseCase
from src.core.exceptions import EntityNotFoundError
from src.domain.entities.calendar_event import CalendarEvent
from src.domain.repositories.calendar_repository import CalendarEventRepository
from src.domain.repositories.google_oauth_token_repository import GoogleOAuthTokenRepository
from src.domain.services.calendar_provider import CalendarProvider


class CreateCalendarEventUseCase:
    def __init__(
        self,
        calendar_repository: CalendarEventRepository,
        calendar_provider: CalendarProvider,
        token_repository: GoogleOAuthTokenRepository,
    ) -> None:
        self._calendar_repository = calendar_repository
        self._calendar_provider = calendar_provider
        self._token_repository = token_repository

    async def execute(self, dto: CreateEventDTO) -> CreateEventResultDTO:
        event = CalendarEvent(
            user_id=dto.user_id,
            title=dto.title,
            start_time=dto.start_time,
            end_time=dto.end_time,
            description=dto.description,
            location=dto.location,
        )

        # --- Détection de conflit avec les événements déjà en cache local ---
        existing_events = await self._calendar_repository.list_by_user(
            dto.user_id, start_range=dto.start_time, end_range=dto.end_time
        )
        conflicts = [e for e in existing_events if e.overlaps_with(event)]

        # --- Synchronisation avec Google Calendar (dégradation gracieuse si non connecté) ---
        try:
            token_use_case = GetValidGoogleAccessTokenUseCase(self._token_repository)
            access_token = await token_use_case.execute(dto.user_id)
            remote_event = await self._calendar_provider.create_event(
                access_token=access_token,
                title=event.title,
                start_time=event.start_time,
                end_time=event.end_time,
                description=event.description,
                location=event.location,
            )
            event.mark_synced(remote_event["id"])
        except EntityNotFoundError:
            # Aucun compte Google connecté : on persiste uniquement en local (synced=False)
            pass

        created = await self._calendar_repository.create(event)

        return CreateEventResultDTO(
            event_id=created.id,
            conflicts=[{"id": str(c.id), "title": c.title, "start_time": c.start_time.isoformat()} for c in conflicts],
        )
