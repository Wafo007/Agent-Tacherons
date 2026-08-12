"""Schémas Pydantic (contrats d'API) pour le module Task."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from src.domain.value_objects.priority import Priority, TaskStatus


class CreateTaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    due_date: Optional[datetime] = None
    priority: Priority = Priority.MEDIUM
    category: str = "general"


class UpdateTaskRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[Priority] = None
    status: Optional[TaskStatus] = None
    category: Optional[str] = None


class TaskResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    description: str
    due_date: Optional[datetime]
    priority: Priority
    status: TaskStatus
    category: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
