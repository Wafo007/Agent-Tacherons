"""Implémentation concrète (Adapter) de TaskRepository avec SQLAlchemy/PostgreSQL."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.task import Task
from src.domain.repositories.task_repository import TaskRepository
from src.domain.value_objects.priority import Priority, TaskStatus
from src.infrastructure.persistence.models.task_model import TaskModel


class SQLAlchemyTaskRepository(TaskRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(model: TaskModel) -> Task:
        return Task(
            id=model.id,
            user_id=model.user_id,
            title=model.title,
            description=model.description,
            due_date=model.due_date,
            priority=Priority(model.priority),
            status=TaskStatus(model.status),
            category=model.category,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_model(entity: Task) -> TaskModel:
        return TaskModel(
            id=entity.id,
            user_id=entity.user_id,
            title=entity.title,
            description=entity.description,
            due_date=entity.due_date,
            priority=entity.priority.value,
            status=entity.status.value,
            category=entity.category,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def create(self, task: Task) -> Task:
        model = self._to_model(task)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, task_id: UUID) -> Optional[Task]:
        result = await self._session.execute(select(TaskModel).where(TaskModel.id == task_id))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_user(
        self,
        user_id: UUID,
        status: Optional[TaskStatus] = None,
        category: Optional[str] = None,
    ) -> List[Task]:
        query = select(TaskModel).where(TaskModel.user_id == user_id)
        if status is not None:
            query = query.where(TaskModel.status == status.value)
        if category is not None:
            query = query.where(TaskModel.category == category)
        result = await self._session.execute(query.order_by(TaskModel.due_date.asc().nullslast()))
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update(self, task: Task) -> Task:
        result = await self._session.execute(select(TaskModel).where(TaskModel.id == task.id))
        model = result.scalar_one()
        model.title = task.title
        model.description = task.description
        model.due_date = task.due_date
        model.priority = task.priority.value
        model.status = task.status.value
        model.category = task.category
        model.updated_at = task.updated_at
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def delete(self, task_id: UUID) -> None:
        await self._session.execute(delete(TaskModel).where(TaskModel.id == task_id))
        await self._session.commit()
