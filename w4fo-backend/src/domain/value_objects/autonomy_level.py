"""
Value Object : AutonomyLevel.

Définit le degré de liberté accordé à l'assistant pour exécuter des actions
sans confirmation explicite de l'utilisateur (voir document d'architecture, §6.4).
"""

from enum import Enum


class AutonomyLevel(str, Enum):
    """Niveau d'autonomie configuré par l'utilisateur pour l'agent IA."""

    LOW = "low"        # Toute action d'écriture nécessite une confirmation
    MEDIUM = "medium"   # Actions réversibles auto-exécutées, actions sensibles confirmées
    HIGH = "high"        # Large autonomie, confirmation uniquement pour les actions irréversibles critiques
