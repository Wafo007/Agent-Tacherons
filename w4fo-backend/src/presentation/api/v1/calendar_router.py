"""
Endpoints du module Agenda : CRUD des événements + flow de connexion OAuth Google Calendar.

Le flow OAuth complet (redirection vers Google, écran de consentement) est
piloté côté client (Flutter) via le SDK/webview Google Sign-In ; ce backend
n'expose que l'échange final du code d'autorisation contre les tokens
(`POST /connect/callback`), conformément à la pratique standard OAuth
Authorization Code — le `client_secret` ne doit jamais transiter côté client.
"""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.application.dto.calendar_dto import CreateEventDTO
from src.application.use_cases.manage_calendar.connect_google_calendar import ConnectGoogleCalendarUseCase
from src.application.use_cases.manage_calendar.create_event import CreateCalendarEventUseCase
from src.application.use_cases.manage_calendar.delete_event import DeleteCalendarEventUseCase
from src.application.use_cases.manage_calendar.list_events import ListCalendarEventsUseCase
from src.application.use_cases.manage_calendar.update_event import UpdateCalendarEventUseCase
from src.core.dependencies import CalendarProviderDep, CalendarRepo, CurrentUserId, GoogleTokenRepo
from src.core.exceptions import EntityNotFoundError
from src.presentation.schemas.calendar_schema import (
    CreateEventRequest,
    CreateEventResponse,
    EventResponse,
    GoogleConnectionStatusResponse,
    GoogleOAuthCallbackRequest,
)

router = APIRouter(prefix="/api/v1/calendar", tags=["calendar"])


# --- Connexion Google Calendar (OAuth) ---


@router.post("/connect/callback", response_model=GoogleConnectionStatusResponse)
async def connect_google_calendar(
    request: GoogleOAuthCallbackRequest, user_id: CurrentUserId, token_repository: GoogleTokenRepo
) -> GoogleConnectionStatusResponse:
    """Finalise la connexion Google Calendar en échangeant le code d'autorisation reçu du client."""
    use_case = ConnectGoogleCalendarUseCase(token_repository)
    await use_case.execute(user_id, request.authorization_code)
    return GoogleConnectionStatusResponse(connected=True)


@router.get("/connect/status", response_model=GoogleConnectionStatusResponse)
async def google_connection_status(
    user_id: CurrentUserId, token_repository: GoogleTokenRepo
) -> GoogleConnectionStatusResponse:
    """Indique si l'utilisateur a déjà connecté son compte Google Calendar."""
    token = await token_repository.get_by_user_id(user_id)
    return GoogleConnectionStatusResponse(connected=token is not None)


@router.delete("/connect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_google_calendar(user_id: CurrentUserId, token_repository: GoogleTokenRepo) -> None:
    """Déconnecte le compte Google Calendar (suppression des tokens stockés)."""
    await token_repository.delete_by_user_id(user_id)


# --- CRUD des événements ---


@router.post("", response_model=CreateEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    request: CreateEventRequest,
    user_id: CurrentUserId,
    calendar_repository: CalendarRepo,
    calendar_provider: CalendarProviderDep,
    token_repository: GoogleTokenRepo,
) -> CreateEventResponse:
    """
    Crée un événement d'agenda. Si des conflits sont détectés avec des événements
    existants, ils sont retournés dans `conflicts` sans bloquer la création
    (voir §6 du document d'architecture — Notifications intelligentes).
    """
    use_case = CreateCalendarEventUseCase(calendar_repository, calendar_provider, token_repository)
    result = await use_case.execute(
        CreateEventDTO(
            user_id=user_id,
            title=request.title,
            start_time=request.start_time,
            end_time=request.end_time,
            description=request.description,
            location=request.location,
        )
    )
    return CreateEventResponse(event_id=result.event_id, conflicts=result.conflicts)


@router.get("", response_model=List[EventResponse])
async def list_events(
    user_id: CurrentUserId,
    calendar_repository: CalendarRepo,
    start_range: Optional[datetime] = None,
    end_range: Optional[datetime] = None,
) -> List[EventResponse]:
    """Liste les événements de l'utilisateur. Par défaut, les 30 prochains jours."""
    use_case = ListCalendarEventsUseCase(calendar_repository)
    events = await use_case.execute(
        user_id,
        start_range=start_range or datetime.utcnow(),
        end_range=end_range or (datetime.utcnow() + timedelta(days=30)),
    )
    return [EventResponse.model_validate(e) for e in events]


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: UUID,
    user_id: CurrentUserId,
    calendar_repository: CalendarRepo,
    calendar_provider: CalendarProviderDep,
    token_repository: GoogleTokenRepo,
    new_start: Optional[datetime] = None,
    new_end: Optional[datetime] = None,
    new_title: Optional[str] = None,
) -> EventResponse:
    use_case = UpdateCalendarEventUseCase(calendar_repository, calendar_provider, token_repository)
    try:
        event = await use_case.execute(event_id, new_start=new_start, new_end=new_end, new_title=new_title)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return EventResponse.model_validate(event)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: UUID,
    calendar_repository: CalendarRepo,
    calendar_provider: CalendarProviderDep,
    token_repository: GoogleTokenRepo,
) -> None:
    use_case = DeleteCalendarEventUseCase(calendar_repository, calendar_provider, token_repository)
    try:
        await use_case.execute(event_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
