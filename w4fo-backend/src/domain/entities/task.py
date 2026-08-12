"""
Entité de domaine : Task.

Porte toutes les règles métier relatives à la gestion d'une tâche :
création, changement de statut, report, priorisation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from src.domain.value_objects.priority import Priority, TaskStatus


@dataclass
class Task:
    """Représente une tâche appartenant à un utilisateur."""

    user_id: UUID
    title: str
    description: str = ""
    due_date: Optional[datetime] = None
    priority: Priority = Priority.MEDIUM
    status: TaskStatus = TaskStatus.TODO
    category: str = "general"
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise ValueError("Le titre d'une tâche ne peut pas être vide.")

    def mark_done(self) -> None:
        """Marque la tâche comme terminée."""
        self.status = TaskStatus.DONE
        self.updated_at = datetime.utcnow()

    def postpone(self, new_due_date: datetime) -> None:
        """Reporte la tâche à une nouvelle date d'échéance."""
        if self.status == TaskStatus.DONE:
            raise ValueError("Impossible de reporter une tâche déjà terminée.")
        self.due_date = new_due_date
        self.status = TaskStatus.POSTPONED
        self.updated_at = datetime.utcnow()

    def change_priority(self, new_priority: Priority) -> None:
        """Modifie la priorité de la tâche."""
        self.priority = new_priority
        self.updated_at = datetime.utcnow()

    def is_overdue(self, reference_time: Optional[datetime] = None) -> bool:
        """Indique si la tâche est en retard par rapport à une date de référence (par défaut: maintenant)."""
        reference = reference_time or datetime.utcnow()
        return (
            self.due_date is not None
            and self.due_date < reference
            and self.status not in (TaskStatus.DONE, TaskStatus.CANCELLED)
        )
