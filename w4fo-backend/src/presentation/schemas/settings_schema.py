"""Schémas Pydantic (contrats d'API) pour les paramètres utilisateur."""

from datetime import time

from pydantic import BaseModel, Field

from src.domain.value_objects.autonomy_level import AutonomyLevel


class UpdateSettingsRequest(BaseModel):
    voice_id: str = "default"
    volume_level: int = Field(default=80, ge=0, le=100)
    briefing_time: time = time(hour=7, minute=30)
    dark_mode: bool = True
    language: str = "fr"
    autonomy_level: AutonomyLevel = AutonomyLevel.MEDIUM


class SettingsResponse(BaseModel):
    voice_id: str
    volume_level: int
    briefing_time: time
    dark_mode: bool
    language: str
    autonomy_level: AutonomyLevel

    model_config = {"from_attributes": True}
