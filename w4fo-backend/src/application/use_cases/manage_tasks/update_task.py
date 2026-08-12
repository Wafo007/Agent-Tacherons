"""Use case : mise à jour d'une tâche existante (titre, statut, priorité, échéance...)."""

from src.application.dto.task_dto import UpdateTaskDTO
from src.core.exceptions import EntityNotFoundError
from src.domain.entities.task import Task
from src.domain.repositories.task_repository import TaskRepository
from src.domain.value_objects.priority import TaskStatus


class UpdateTaskUseCase:
    def __init__(self, task_repository: TaskRepository) -> None:
        self._task_repository = task_repository

    async def execute(self, dto: UpdateTaskDTO) -> Task:
        task = await self._task_repository.get_by_id(dto.task_id)
        if task is None:
            raise EntityNotFoundError(f"Tâche {dto.task_id} introuvable.")

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
