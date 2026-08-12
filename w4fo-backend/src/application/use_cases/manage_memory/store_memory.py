"""Use case : enregistre un nouveau souvenir en mémoire long terme, avec calcul d'embedding."""

from dataclasses import dataclass
from uuid import UUID

from src.domain.entities.memory import Memory
from src.domain.repositories.memory_repository import MemoryRepository
from src.domain.services.llm_provider import LLMProvider
from src.domain.value_objects.memory_type import MemoryType


@dataclass
class StoreMemoryDTO:
    user_id: UUID
    content: str
    memory_type: MemoryType
    importance_score: float = 0.5


class StoreMemoryUseCase:
    def __init__(self, memory_repository: MemoryRepository, llm_provider: LLMProvider) -> None:
        self._memory_repository = memory_repository
        self._llm_provider = llm_provider

    async def execute(self, dto: StoreMemoryDTO) -> Memory:
        embedding = await self._llm_provider.embed(dto.content)

        memory = Memory(
            user_id=dto.user_id,
            content=dto.content,
            memory_type=dto.memory_type,
            importance_score=dto.importance_score,
            expires_at=Memory.default_expiry_for(dto.memory_type),
        )
        return await self._memory_repository.create(memory, embedding)
