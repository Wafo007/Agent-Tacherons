"""Use case : mise à jour d'une tâche existante (titre, statut, priorité, échéance...)."""

from uuid import UUID

from src.application.dto.task_dto import UpdateTaskDTO
from src.core.exceptions import EntityNotFoundError, UnauthorizedError
from src.domain.entities.task import Task
from src.domain.repositories.task_repository import TaskRepository
from src.domain.value_objects.priority import TaskStatus


class UpdateTaskUseCase:
    def __init__(self, task_repository: TaskRepository) -> None:
        self._task_repository = task_repository

    async def execute(self, dto: UpdateTaskDTO, user_id: UUID) -> Task:
        """
        `user_id` est OBLIGATOIRE (§ AUDIT : le contrôle d'appartenance était
        absent avant ce correctif, un `task_id` valide de n'importe quel
        utilisateur pouvait être modifié). Lève `UnauthorizedError` si la
        tâche appartient à un autre utilisateur.
        """
        task = await self._task_repository.get_by_id(dto.task_id)
        if task is None:
            raise EntityNotFoundError(f"Tâche {dto.task_id} introuvable.")
        if task.user_id != user_id:
            raise UnauthorizedError("Cette tâche n'appartient pas à cet utilisateur.")

        if dto.title is not None:
            task.title = dto.title
        if dto.description is not None:
            task.description = dto.description
        if dto.due_date is not None:
            task.due_date = dto.due_date
        if dto.priority is not None:
            task.change_priority(dto.priority)
        if dto.category is not None:
            task.category = dto.category
        if dto.status is not None:
            if dto.status == TaskStatus.DONE:
                task.mark_done()
            else:
                task.status = dto.status

        return await self._task_repository.update(task)
