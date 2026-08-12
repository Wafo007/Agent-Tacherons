"""Use case : suppression d'une tâche."""

from uuid import UUID

from src.core.exceptions import EntityNotFoundError
from src.domain.repositories.task_repository import TaskRepository


class DeleteTaskUseCase:
    def __init__(self, task_repository: TaskRepository) -> None:
        self._task_repository = task_repository

    async def execute(self, task_id: UUID) -> None:
        task = await self._task_repository.get_by_id(task_id)
        if task is None:
            raise EntityNotFoundError(f"Tâche {task_id} introuvable.")
        await self._task_repository.delete(task_id)
