"""
DTOs (Data Transfer Objects) pour le module Task.

Ces objets transitent entre la couche présentation et la couche application.
Ils évitent d'exposer directement les entités de domaine à l'extérieur,
et découplent le contrat d'API des règles métier internes.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from src.domain.value_objects.priority import Priority, TaskStatus


@dataclass
class CreateTaskDTO:
    user_id: UUID
    title: str
    description: str = ""
    due_date: Optional[datetime] = None
    priority: Priority = Priority.MEDIUM
    category: str = "general"


@dataclass
class UpdateTaskDTO:
    task_id: UUID
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[Priority] = None
    status: Optional[TaskStatus] = None
    category: Optional[str] = None
