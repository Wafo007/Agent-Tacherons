"""Implémentation concrète (Adapter) de UserSettingsRepository avec SQLAlchemy/PostgreSQL."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.user_settings import UserSettings
from src.domain.repositories.user_settings_repository import UserSettingsRepository
from src.domain.value_objects.autonomy_level import AutonomyLevel
from src.infrastructure.persistence.models.user_settings_model import UserSettingsModel


class SQLAlchemyUserSettingsRepository(UserSettingsRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(model: UserSettingsModel) -> UserSettings:
        return UserSettings(
            id=model.id,
            user_id=model.user_id,
            voice_id=model.voice_id,
            volume_level=model.volume_level,
            briefing_time=model.briefing_time,
            dark_mode=model.dark_mode,
            language=model.language,
            autonomy_level=AutonomyLevel(model.autonomy_level),
        )

    async def get_by_user_id(self, user_id: UUID) -> Optional[UserSettings]:
        result = await self._session.execute(select(UserSettingsModel).where(UserSettingsModel.user_id == user_id))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def upsert(self, settings: UserSettings) -> UserSettings:
        result = await self._session.execute(
            select(UserSettingsModel).where(UserSettingsModel.user_id == settings.user_id)
        )
        model = result.scalar_one_or_none()

        if model is None:
            model = UserSettingsModel(id=settings.id, user_id=settings.user_id)
            self._session.add(model)

        model.voice_id = settings.voice_id
        model.volume_level = settings.volume_level
        model.briefing_time = settings.briefing_time
        model.dark_mode = settings.dark_mode
        model.language = settings.language
        model.autonomy_level = settings.autonomy_level.value

        await self._session.commit()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def list_all(self) -> List[UserSettings]:
        result = await self._session.execute(select(UserSettingsModel))
        return [self._to_entity(m) for m in result.scalars().all()]
