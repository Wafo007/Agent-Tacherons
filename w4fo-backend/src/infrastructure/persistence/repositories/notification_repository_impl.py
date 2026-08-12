"""Implémentation concrète (Adapter) de NotificationRepository avec SQLAlchemy/PostgreSQL."""

from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.notification import Notification
from src.domain.repositories.notification_repository import NotificationRepository
from src.infrastructure.persistence.models.notification_model import NotificationModel


class SQLAlchemyNotificationRepository(NotificationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(model: NotificationModel) -> Notification:
        return Notification(
            id=model.id,
            user_id=model.user_id,
            type=model.type,
            title=model.title,
            message=model.message,
            related_entity_type=model.related_entity_type,
            related_entity_id=model.related_entity_id,
            is_read=model.is_read,
            created_at=model.created_at,
        )

    async def create(self, notification: Notification) -> Notification:
        model = NotificationModel(
            id=notification.id,
            user_id=notification.user_id,
            type=notification.type,
            title=notification.title,
            message=notification.message,
            related_entity_type=notification.related_entity_type,
            related_entity_id=notification.related_entity_id,
            is_read=notification.is_read,
            created_at=notification.created_at,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def list_by_user(self, user_id: UUID, unread_only: bool = False) -> List[Notification]:
        query = select(NotificationModel).where(NotificationModel.user_id == user_id)
        if unread_only:
            query = query.where(NotificationModel.is_read.is_(False))
        result = await self._session.execute(query.order_by(NotificationModel.created_at.desc()))
        return [self._to_entity(m) for m in result.scalars().all()]

    async def mark_as_read(self, notification_id: UUID) -> None:
        result = await self._session.execute(select(NotificationModel).where(NotificationModel.id == notification_id))
        model = result.scalar_one()
        model.is_read = True
        await self._session.commit()
