"""Use case : suppression d'une tâche."""

from uuid import UUID

from src.core.exceptions import EntityNotFoundError, UnauthorizedError
from src.domain.repositories.task_repository import TaskRepository


class DeleteTaskUseCase:
    def __init__(self, task_repository: TaskRepository) -> None:
        self._task_repository = task_repository

    async def execute(self, task_id: UUID, user_id: UUID) -> None:
        """
        `user_id` est OBLIGATOIRE (même correctif que `UpdateTaskUseCase`,
        voir § AUDIT) : lève `UnauthorizedError` si la tâche appartient à un
        autre utilisateur, plutôt que de la supprimer silencieusement.
        """
        task = await self._task_repository.get_by_id(task_id)
        if task is None:
            raise EntityNotFoundError(f"Tâche {task_id} introuvable.")
        if task.user_id != user_id:
            raise UnauthorizedError("Cette tâche n'appartient pas à cet utilisateur.")
        await self._task_repository.delete(task_id)
