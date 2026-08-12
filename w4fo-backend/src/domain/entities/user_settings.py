"""Entité de domaine : UserSettings — paramètres utilisateur (§2 du document d'architecture)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from uuid import UUID, uuid4

from src.domain.value_objects.autonomy_level import AutonomyLevel


@dataclass
class UserSettings:
    """Paramètres personnalisables de l'assistant pour un utilisateur donné."""

    user_id: UUID
    voice_id: str = "default"
    volume_level: int = 80
    briefing_time: time = field(default_factory=lambda: time(hour=7, minute=30))
    dark_mode: bool = True
    language: str = "fr"
    autonomy_level: AutonomyLevel = AutonomyLevel.MEDIUM
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not 0 <= self.volume_level <= 100:
            raise ValueError("Le volume doit être compris entre 0 et 100.")
