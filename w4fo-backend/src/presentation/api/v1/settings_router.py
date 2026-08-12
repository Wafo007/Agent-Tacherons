"""
Endpoints de gestion des paramètres utilisateur (§2 et §8 du document
d'architecture — module `settings`) : voix, volume, heure de briefing,
thème, langue, niveau d'autonomie de l'assistant.
"""

from fastapi import APIRouter

from src.core.dependencies import CurrentUserId, UserSettingsRepo
from src.domain.entities.user_settings import UserSettings
from src.presentation.schemas.settings_schema import SettingsResponse, UpdateSettingsRequest

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings(user_id: CurrentUserId, settings_repository: UserSettingsRepo) -> SettingsResponse:
    """Retourne les paramètres de l'utilisateur, ou les valeurs par défaut si jamais configurés."""
    settings = await settings_repository.get_by_user_id(user_id)
    if settings is None:
        settings = UserSettings(user_id=user_id)  # Valeurs par défaut, non persistées tant que non modifiées
    return SettingsResponse.model_validate(settings)


@router.put("", response_model=SettingsResponse)
async def update_settings(
    request: UpdateSettingsRequest, user_id: CurrentUserId, settings_repository: UserSettingsRepo
) -> SettingsResponse:
    """Met à jour (ou crée) les paramètres de l'utilisateur."""
    settings = UserSettings(
        user_id=user_id,
        voice_id=request.voice_id,
        volume_level=request.volume_level,
        briefing_time=request.briefing_time,
        dark_mode=request.dark_mode,
        language=request.language,
        autonomy_level=request.autonomy_level,
    )
    updated = await settings_repository.upsert(settings)
    return SettingsResponse.model_validate(updated)
