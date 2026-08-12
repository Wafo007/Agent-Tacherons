"""
Interface (Port) : MemoryRepository.

La recherche sémantique (`search_similar`) prend un embedding déjà calculé en
entrée plutôt qu'un texte brut : le domaine ne sait pas comment calculer un
embedding (c'est la responsabilité de `LLMProvider.embed`, appelée par le use
case applicatif), il ne fait que rechercher par similarité vectorielle.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from src.domain.entities.memory import Memory
from src.domain.value_objects.memory_type import MemoryType


class MemoryRepository(ABC):
    """Contrat de persistance et de recherche sémantique pour l'entité Memory."""

    @abstractmethod
    async def create(self, memory: Memory, embedding: list[float]) -> Memory:
        raise NotImplementedError

    @abstractmethod
    async def search_similar(
        self,
        user_id: UUID,
        query_embedding: list[float],
        top_k: int = 5,
        memory_type: Optional[MemoryType] = None,
    ) -> List[Memory]:
        """Recherche les souvenirs les plus proches sémantiquement d'un embedding de requête."""
        raise NotImplementedError

    @abstractmethod
    async def list_by_user(self, user_id: UUID, memory_type: Optional[MemoryType] = None) -> List[Memory]:
        raise NotImplementedError

    @abstractmethod
    async def update(self, memory: Memory) -> Memory:
        raise NotImplementedError

    @abstractmethod
    async def delete_expired(self, user_id: UUID) -> int:
        """Supprime les souvenirs expirés d'un utilisateur et retourne le nombre supprimé."""
        raise NotImplementedError
