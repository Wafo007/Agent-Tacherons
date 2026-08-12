"""
Interface (Port) : CalendarProvider.

Abstrait le fournisseur d'agenda externe (Google Calendar en V2). Distincte de
`CalendarEventRepository` : le repository gère le cache local (PostgreSQL),
tandis que ce provider gère la synchronisation avec le service tiers.
Cette séparation permet un fonctionnement en mode dégradé (lecture du cache
local) si Google Calendar est temporairement indisponible.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional


class CalendarProvider(ABC):
    """Contrat pour un fournisseur d'agenda externe (ex. Google Calendar)."""

    @abstractmethod
    async def list_events(
        self, access_token: str, start_range: datetime, end_range: datetime
    ) -> list[dict[str, Any]]:
        """Liste les événements distants sur une plage temporelle donnée."""
        raise NotImplementedError

    @abstractmethod
    async def create_event(
        self,
        access_token: str,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: str = "",
        location: str = "",
    ) -> dict[str, Any]:
        """Crée un événement distant et retourne sa représentation (incluant l'ID Google)."""
        raise NotImplementedError

    @abstractmethod
    async def update_event(
        self,
        access_token: str,
        google_event_id: str,
        title: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """Met à jour un événement distant existant."""
        raise NotImplementedError

    @abstractmethod
    async def delete_event(self, access_token: str, google_event_id: str) -> None:
        """Supprime un événement distant."""
        raise NotImplementedError
