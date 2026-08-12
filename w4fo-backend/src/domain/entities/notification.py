"""Entité de domaine : Notification (§6 du document d'architecture — Notifications intelligentes)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4


@dataclass
class Notification:
    """Représente une notification proactive générée par l'assistant."""

    user_id: UUID
    type: str  # ex: "morning_briefing", "task_overdue", "calendar_conflict"
    title: str
    message: str
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[UUID] = None
    is_read: bool = False
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def mark_read(self) -> None:
        self.is_read = True
