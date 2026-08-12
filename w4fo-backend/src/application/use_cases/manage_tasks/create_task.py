"""Use case : création d'une nouvelle tâche pour un utilisateur."""

from src.application.dto.task_dto import CreateTaskDTO
from src.domain.entities.task import Task
from src.domain.repositories.task_repository import TaskRepository


class CreateTaskUseCase:
    """Orchestre la création d'une tâche : validation métier + persistance."""

    def __init__(self, task_repository: TaskRepository) -> None:
        self._task_repository = task_repository

    async def execute(self, dto: CreateTaskDTO) -> Task:
        task = Task(
            user_id=dto.user_id,
            title=dto.title,
            description=dto.description,
            due_date=dto.due_date,
            priority=dto.priority,
            category=dto.category,
        )
        return await self._task_repository.create(task)
