"""
Entité de domaine : Memory.

Représente un élément de mémoire long terme (fait, préférence, habitude, objectif,
résumé de conversation) — voir §6.5 du document d'architecture. L'embedding
vectoriel n'est PAS stocké dans cette entité pure : il est calculé et manipulé
uniquement côté infrastructure (le domaine ne connaît pas la notion de "vecteur
d'embedding", qui est un détail technique du moteur de recherche sémantique).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

from src.domain.value_objects.memory_type import MemoryType


@dataclass
class Memory:
    """Représente un souvenir mémorisé par l'assistant pour un utilisateur donné."""

    user_id: UUID
    content: str
    memory_type: MemoryType
    importance_score: float = 0.5
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.content or not self.content.strip():
            raise ValueError("Le contenu d'un souvenir ne peut pas être vide.")
        if not 0.0 <= self.importance_score <= 1.0:
            raise ValueError("Le score d'importance doit être compris entre 0 et 1.")

    def touch(self) -> None:
        """Marque le souvenir comme récemment accédé (utilisé pour les stratégies d'oubli progressif)."""
        self.last_accessed_at = datetime.utcnow()

    def reinforce(self, increment: float = 0.1) -> None:
        """Augmente l'importance du souvenir (ex: mentionné à nouveau par l'utilisateur)."""
        self.importance_score = min(1.0, self.importance_score + increment)

    def is_expired(self, reference_time: Optional[datetime] = None) -> bool:
        reference = reference_time or datetime.utcnow()
        return self.expires_at is not None and self.expires_at <= reference

    @staticmethod
    def default_expiry_for(memory_type: MemoryType) -> Optional[datetime]:
        """
        Politique de rétention par défaut selon le type de souvenir (§13, risque de
        dérive mémoire). Les faits/préférences/objectifs sont conservés indéfiniment ;
        les résumés de conversation expirent après 90 jours pour limiter la croissance.
        """
        if memory_type == MemoryType.CONVERSATION_SUMMARY:
            return datetime.utcnow() + timedelta(days=90)
        return None
