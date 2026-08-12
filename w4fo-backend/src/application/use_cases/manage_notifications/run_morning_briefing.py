"""
Use case : exécute le briefing matinal pour un utilisateur et persiste le
résultat comme notification (consommée par le client au prochain sync, ou
poussée en temps réel si l'app est ouverte — mécanisme de push à raffiner
en V3 avec un canal WebSocket de notifications dédié).
"""

from uuid import UUID

from src.application.use_cases.generate_morning_briefing import GenerateMorningBriefingUseCase
from src.domain.entities.notification import Notification
from src.domain.repositories.calendar_repository import CalendarEventRepository
from src.domain.repositories.notification_repository import NotificationRepository
from src.domain.repositories.task_repository import TaskRepository
from src.domain.services.llm_provider import LLMProvider


class RunMorningBriefingForUserUseCase:
    def __init__(
        self,
        task_repository: TaskRepository,
        calendar_repository: CalendarEventRepository,
        notification_repository: NotificationRepository,
        llm_provider: LLMProvider,
    ) -> None:
        self._task_repository = task_repository
        self._calendar_repository = calendar_repository
        self._notification_repository = notification_repository
        self._llm_provider = llm_provider

    async def execute(self, user_id: UUID) -> Notification:
        briefing_use_case = GenerateMorningBriefingUseCase(
            self._task_repository, self._calendar_repository, self._llm_provider
        )
        result = await briefing_use_case.execute(user_id)

        notification = Notification(
            user_id=user_id,
            type="morning_briefing",
            title="Votre briefing du matin",
            message=result.briefing_text,
        )
        return await self._notification_repository.create(notification)
