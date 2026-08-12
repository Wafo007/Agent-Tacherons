"""Use case : recherche sémantique des souvenirs pertinents pour une requête donnée."""

from typing import List
from uuid import UUID

from src.domain.entities.memory import Memory
from src.domain.repositories.memory_repository import MemoryRepository
from src.domain.services.llm_provider import LLMProvider


class SearchRelevantMemoriesUseCase:
    """
    Recherche les souvenirs les plus pertinents pour contextualiser une conversation
    (appelée en tout début de tour, voir §6.5 du document d'architecture — "Mémoire
    dans le graphe"). Met également à jour `last_accessed_at` sur les souvenirs
    utilisés (utile pour une future stratégie d'oubli progressif basée sur la
    fraîcheur d'accès).
    """

    def __init__(self, memory_repository: MemoryRepository, llm_provider: LLMProvider) -> None:
        self._memory_repository = memory_repository
        self._llm_provider = llm_provider

    async def execute(self, user_id: UUID, query_text: str, top_k: int = 5) -> List[Memory]:
        query_embedding = await self._llm_provider.embed(query_text)
        memories = await self._memory_repository.search_similar(user_id, query_embedding, top_k=top_k)

        for memory in memories:
            memory.touch()
            await self._memory_repository.update(memory)

        return memories
