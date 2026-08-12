"""Interface (Port) : NotificationRepository."""

from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from src.domain.entities.notification import Notification


class NotificationRepository(ABC):
    @abstractmethod
    async def create(self, notification: Notification) -> Notification:
        raise NotImplementedError

    @abstractmethod
    async def list_by_user(self, user_id: UUID, unread_only: bool = False) -> List[Notification]:
        raise NotImplementedError

    @abstractmethod
    async def mark_as_read(self, notification_id: UUID) -> None:
        raise NotImplementedError
