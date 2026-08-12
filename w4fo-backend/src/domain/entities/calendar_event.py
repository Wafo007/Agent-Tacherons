"""
Entité de domaine : CalendarEvent.

Représente un événement d'agenda, indépendamment de Google Calendar ou de
tout autre fournisseur. Porte les règles métier de détection de conflit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4


@dataclass
class CalendarEvent:
    """Représente un événement d'agenda appartenant à un utilisateur."""

    user_id: UUID
    title: str
    start_time: datetime
    end_time: datetime
    description: str = ""
    location: str = ""
    google_event_id: Optional[str] = None
    synced: bool = False
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise ValueError("Le titre d'un événement ne peut pas être vide.")
        if self.end_time <= self.start_time:
            raise ValueError("La date de fin doit être postérieure à la date de début.")

    def overlaps_with(self, other: "CalendarEvent") -> bool:
        """Indique si cet événement chevauche un autre (détection de conflit d'agenda)."""
        return self.start_time < other.end_time and other.start_time < self.end_time

    def mark_synced(self, google_event_id: str) -> None:
        """Marque l'événement comme synchronisé avec Google Calendar."""
        self.google_event_id = google_event_id
        self.synced = True

    def reschedule(self, new_start: datetime, new_end: datetime) -> None:
        """Déplace l'événement à un nouveau créneau."""
        if new_end <= new_start:
            raise ValueError("La date de fin doit être postérieure à la date de début.")
        self.start_time = new_start
        self.end_time = new_end
        self.synced = False  # Nécessite une re-synchronisation avec Google Calendar
