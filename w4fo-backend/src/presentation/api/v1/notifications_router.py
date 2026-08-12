"""
Endpoints de consultation des notifications proactives (§6 du document
d'architecture). Le client (Flutter) est censé poller cet endpoint
périodiquement en V2 ; un canal de push temps réel (WebSocket dédié ou
notifications push natives) est prévu en V3.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Query

from src.core.dependencies import CurrentUserId, NotificationRepo
from src.presentation.schemas.notification_schema import NotificationResponse

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("", response_model=List[NotificationResponse])
async def list_notifications(
    user_id: CurrentUserId,
    notification_repository: NotificationRepo,
    unread_only: bool = Query(default=False),
) -> List[NotificationResponse]:
    notifications = await notification_repository.list_by_user(user_id, unread_only=unread_only)
    return [NotificationResponse.model_validate(n) for n in notifications]


@router.post("/{notification_id}/read", status_code=204)
async def mark_notification_read(notification_id: UUID, notification_repository: NotificationRepo) -> None:
    await notification_repository.mark_as_read(notification_id)
