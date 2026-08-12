"""DTOs pour le module Calendar."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class CreateEventDTO:
    user_id: UUID
    title: str
    start_time: datetime
    end_time: datetime
    description: str = ""
    location: str = ""


@dataclass
class CreateEventResultDTO:
    event_id: UUID
    conflicts: list[dict] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.conflicts is None:
            self.conflicts = []
