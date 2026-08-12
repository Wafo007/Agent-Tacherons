"""
Interface (Port) : TaskRepository.

Contrat de persistance pour l'entité Task, indépendant de toute technologie.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from src.domain.entities.task import Task
from src.domain.value_objects.priority import TaskStatus


class TaskRepository(ABC):
    """Contrat de persistance pour l'entité Task."""

    @abstractmethod
    async def create(self, task: Task) -> Task:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, task_id: UUID) -> Optional[Task]:
        raise NotImplementedError

    @abstractmethod
    async def list_by_user(
        self,
        user_id: UUID,
        status: Optional[TaskStatus] = None,
        category: Optional[str] = None,
    ) -> List[Task]:
        """Liste les tâches d'un utilisateur, avec filtres optionnels."""
        raise NotImplementedError

    @abstractmethod
    async def update(self, task: Task) -> Task:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, task_id: UUID) -> None:
        raise NotImplementedError
