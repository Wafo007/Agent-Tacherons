"""Implémentation concrète (Adapter) de CalendarEventRepository avec SQLAlchemy/PostgreSQL."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.calendar_event import CalendarEvent
from src.domain.repositories.calendar_repository import CalendarEventRepository
from src.infrastructure.persistence.models.calendar_event_model import CalendarEventModel


class SQLAlchemyCalendarEventRepository(CalendarEventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(model: CalendarEventModel) -> CalendarEvent:
        return CalendarEvent(
            id=model.id,
            user_id=model.user_id,
            title=model.title,
            description=model.description,
            start_time=model.start_time,
            end_time=model.end_time,
            location=model.location,
            google_event_id=model.google_event_id,
            synced=model.synced,
            created_at=model.created_at,
        )

    @staticmethod
    def _to_model(entity: CalendarEvent) -> CalendarEventModel:
        return CalendarEventModel(
            id=entity.id,
            user_id=entity.user_id,
            title=entity.title,
            description=entity.description,
            start_time=entity.start_time,
            end_time=entity.end_time,
            location=entity.location,
            google_event_id=entity.google_event_id,
            synced=entity.synced,
            created_at=entity.created_at,
        )

    async def create(self, event: CalendarEvent) -> CalendarEvent:
        model = self._to_model(event)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, event_id: UUID) -> Optional[CalendarEvent]:
        result = await self._session.execute(select(CalendarEventModel).where(CalendarEventModel.id == event_id))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_user(
        self,
        user_id: UUID,
        start_range: Optional[datetime] = None,
        end_range: Optional[datetime] = None,
    ) -> List[CalendarEvent]:
        query = select(CalendarEventModel).where(CalendarEventModel.user_id == user_id)
        if start_range is not None:
            query = query.where(CalendarEventModel.end_time >= start_range)
        if end_range is not None:
            query = query.where(CalendarEventModel.start_time <= end_range)
        result = await self._session.execute(query.order_by(CalendarEventModel.start_time.asc()))
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update(self, event: CalendarEvent) -> CalendarEvent:
        result = await self._session.execute(select(CalendarEventModel).where(CalendarEventModel.id == event.id))
        model = result.scalar_one()
        model.title = event.title
        model.description = event.description
        model.start_time = event.start_time
        model.end_time = event.end_time
        model.location = event.location
        model.google_event_id = event.google_event_id
        model.synced = event.synced
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def delete(self, event_id: UUID) -> None:
        await self._session.execute(delete(CalendarEventModel).where(CalendarEventModel.id == event_id))
        await self._session.commit()
