"""Use case : lister les tâches d'un utilisateur, avec filtres optionnels."""

from typing import List, Optional
from uuid import UUID

from src.domain.entities.task import Task
from src.domain.repositories.task_repository import TaskRepository
from src.domain.value_objects.priority import TaskStatus


class ListTasksUseCase:
    def __init__(self, task_repository: TaskRepository) -> None:
        self._task_repository = task_repository

    async def execute(
        self,
        user_id: UUID,
        status: Optional[TaskStatus] = None,
        category: Optional[str] = None,
    ) -> List[Task]:
        return await self._task_repository.list_by_user(user_id, status=status, category=category)
