"""
Outils (tools) du module Agenda, exposés au LLM via function calling.

`calendar_delete` est classé comme action sensible (§6.4) : la suppression d'un
rendez-vous peut impacter un tiers (RDV partagé), donc confirmation requise.
`calendar_create` reste non-sensible : la détection de conflit (retournée dans
l'observation) permet au LLM d'alerter l'utilisateur sans bloquer l'action.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from src.application.dto.calendar_dto import CreateEventDTO
from src.application.use_cases.manage_calendar.create_event import CreateCalendarEventUseCase
from src.application.use_cases.manage_calendar.delete_event import DeleteCalendarEventUseCase
from src.application.use_cases.manage_calendar.list_events import ListCalendarEventsUseCase
from src.domain.repositories.calendar_repository import CalendarEventRepository
from src.domain.repositories.google_oauth_token_repository import GoogleOAuthTokenRepository
from src.domain.services.calendar_provider import CalendarProvider

SENSITIVE_CALENDAR_TOOLS: set[str] = {"calendar_delete"}

CALENDAR_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "calendar_create",
            "description": "Crée un nouvel événement dans l'agenda de l'utilisateur. Détecte automatiquement les conflits.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Titre de l'événement."},
                    "start_time": {"type": "string", "description": "Date/heure de début au format ISO 8601."},
                    "end_time": {"type": "string", "description": "Date/heure de fin au format ISO 8601."},
                    "description": {"type": "string"},
                    "location": {"type": "string"},
                },
                "required": ["title", "start_time", "end_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calendar_list",
            "description": "Liste les événements de l'agenda sur une plage de dates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_range": {"type": "string", "description": "Début de la plage, format ISO 8601."},
                    "end_range": {"type": "string", "description": "Fin de la plage, format ISO 8601."},
                },
                "required": ["start_range", "end_range"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calendar_delete",
            "description": "Supprime un événement de l'agenda. Action sensible nécessitant confirmation.",
            "parameters": {
                "type": "object",
                "properties": {"event_id": {"type": "string", "description": "Identifiant UUID de l'événement."}},
                "required": ["event_id"],
            },
        },
    },
]


async def execute_calendar_tool(
    tool_name: str,
    arguments: dict[str, Any],
    user_id: UUID,
    calendar_repository: CalendarEventRepository,
    calendar_provider: CalendarProvider,
    token_repository: GoogleOAuthTokenRepository,
) -> dict[str, Any]:
    """Exécute un outil Calendar par son nom, en déléguant au use case applicatif approprié."""
    if tool_name == "calendar_create":
        use_case = CreateCalendarEventUseCase(calendar_repository, calendar_provider, token_repository)
        result = await use_case.execute(
            CreateEventDTO(
                user_id=user_id,
                title=arguments["title"],
                start_time=datetime.fromisoformat(arguments["start_time"]),
                end_time=datetime.fromisoformat(arguments["end_time"]),
                description=arguments.get("description", ""),
                location=arguments.get("location", ""),
            )
        )
        return {"event_id": str(result.event_id), "conflicts": result.conflicts}

    if tool_name == "calendar_list":
        use_case = ListCalendarEventsUseCase(calendar_repository)
        events = await use_case.execute(
            user_id,
            start_range=datetime.fromisoformat(arguments["start_range"]),
            end_range=datetime.fromisoformat(arguments["end_range"]),
        )
        return {
            "events": [
                {"id": str(e.id), "title": e.title, "start_time": e.start_time.isoformat(), "end_time": e.end_time.isoformat()}
                for e in events
            ]
        }

    if tool_name == "calendar_delete":
        use_case = DeleteCalendarEventUseCase(calendar_repository, calendar_provider, token_repository)
        await use_case.execute(UUID(arguments["event_id"]))
        return {"deleted": True, "event_id": arguments["event_id"]}

    raise ValueError(f"Outil inconnu : {tool_name}")
