"""
Implémentation concrète (Adapter) de CalendarProvider avec l'API Google Calendar.

Utilise directement l'API REST Google Calendar via httpx (plutôt que le SDK
google-api-python-client, synchrone et plus lourd), pour rester cohérent avec
l'architecture full-async du backend. Le token d'accès OAuth est fourni par
l'appelant (récupéré depuis le stockage chiffré de l'utilisateur, voir §11 du
document d'architecture) — cette classe ne gère pas le cycle de vie du token.
"""

from datetime import datetime
from typing import Any, Optional

import httpx

from src.domain.services.calendar_provider import CalendarProvider

GOOGLE_CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"


class GoogleCalendarProvider(CalendarProvider):
    """Fournisseur d'agenda basé sur l'API Google Calendar (calendrier `primary`)."""

    def __init__(self, calendar_id: str = "primary") -> None:
        self._calendar_id = calendar_id

    @staticmethod
    def _headers(access_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    async def list_events(
        self, access_token: str, start_range: datetime, end_range: datetime
    ) -> list[dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GOOGLE_CALENDAR_API_BASE}/calendars/{self._calendar_id}/events",
                headers=self._headers(access_token),
                params={
                    "timeMin": start_range.isoformat(),
                    "timeMax": end_range.isoformat(),
                    "singleEvents": "true",
                    "orderBy": "startTime",
                },
            )
            response.raise_for_status()
            return response.json().get("items", [])

    async def create_event(
        self,
        access_token: str,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: str = "",
        location: str = "",
    ) -> dict[str, Any]:
        payload = {
            "summary": title,
            "description": description,
            "location": location,
            "start": {"dateTime": start_time.isoformat()},
            "end": {"dateTime": end_time.isoformat()},
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GOOGLE_CALENDAR_API_BASE}/calendars/{self._calendar_id}/events",
                headers=self._headers(access_token),
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def update_event(
        self,
        access_token: str,
        google_event_id: str,
        title: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if title is not None:
            payload["summary"] = title
        if start_time is not None:
            payload["start"] = {"dateTime": start_time.isoformat()}
        if end_time is not None:
            payload["end"] = {"dateTime": end_time.isoformat()}

        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{GOOGLE_CALENDAR_API_BASE}/calendars/{self._calendar_id}/events/{google_event_id}",
                headers=self._headers(access_token),
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def delete_event(self, access_token: str, google_event_id: str) -> None:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{GOOGLE_CALENDAR_API_BASE}/calendars/{self._calendar_id}/events/{google_event_id}",
                headers=self._headers(access_token),
            )
            # 404 = déjà supprimé côté Google, on ne considère pas cela comme une erreur bloquante
            if response.status_code not in (200, 204, 404):
                response.raise_for_status()
