"""
Value Objects liés aux tâches : Priority et TaskStatus.

Un Value Object est un objet sans identité propre, défini uniquement par sa valeur.
On utilise des Enum ici pour garantir que seules des valeurs métier valides
puissent circuler dans le domaine (évite les "magic strings" partout dans le code).
"""

from enum import Enum


class Priority(str, Enum):
    """Niveau de priorité d'une tâche."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(str, Enum):
    """Statut d'avancement d'une tâche."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"
