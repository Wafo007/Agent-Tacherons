"""
Implémentation concrète (Adapter) de MemoryRepository avec SQLAlchemy/pgvector.

Utilise l'opérateur de distance cosinus de pgvector (`cosine_distance`, via
`Vector.cosine_distance` exposé par le mapping SQLAlchemy) pour le classement
par similarité — cohérent avec les embeddings normalisés produits par les
modèles de type `mistral-embed`.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.memory import Memory
from src.domain.repositories.memory_repository import MemoryRepository
from src.domain.value_objects.memory_type import MemoryType
from src.infrastructure.persistence.models.memory_model import MemoryModel


class SQLAlchemyMemoryRepository(MemoryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(model: MemoryModel) -> Memory:
        return Memory(
            id=model.id,
            user_id=model.user_id,
            content=model.content,
            memory_type=MemoryType(model.memory_type),
            importance_score=model.importance_score,
            created_at=model.created_at,
            last_accessed_at=model.last_accessed_at,
            expires_at=model.expires_at,
        )

    async def create(self, memory: Memory, embedding: list[float]) -> Memory:
        model = MemoryModel(
            id=memory.id,
            user_id=memory.user_id,
            memory_type=memory.memory_type.value,
            content=memory.content,
            embedding=embedding,
            importance_score=memory.importance_score,
            created_at=memory.created_at,
            last_accessed_at=memory.last_accessed_at,
            expires_at=memory.expires_at,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def search_similar(
        self,
        user_id: UUID,
        query_embedding: list[float],
        top_k: int = 5,
        memory_type: Optional[MemoryType] = None,
    ) -> List[Memory]:
        query = select(MemoryModel).where(MemoryModel.user_id == user_id)
        if memory_type is not None:
            query = query.where(MemoryModel.memory_type == memory_type.value)

        # Classement par distance cosinus croissante (le plus similaire en premier)
        query = query.order_by(MemoryModel.embedding.cosine_distance(query_embedding)).limit(top_k)

        result = await self._session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def list_by_user(self, user_id: UUID, memory_type: Optional[MemoryType] = None) -> List[Memory]:
        query = select(MemoryModel).where(MemoryModel.user_id == user_id)
        if memory_type is not None:
            query = query.where(MemoryModel.memory_type == memory_type.value)
        result = await self._session.execute(query.order_by(MemoryModel.created_at.desc()))
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update(self, memory: Memory) -> Memory:
        result = await self._session.execute(select(MemoryModel).where(MemoryModel.id == memory.id))
        model = result.scalar_one()
        model.content = memory.content
        model.importance_score = memory.importance_score
        model.last_accessed_at = memory.last_accessed_at
        model.expires_at = memory.expires_at
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def delete_expired(self, user_id: UUID) -> int:
        now = datetime.utcnow()
        result = await self._session.execute(
            delete(MemoryModel)
            .where(MemoryModel.user_id == user_id)
            .where(MemoryModel.expires_at.is_not(None))
            .where(MemoryModel.expires_at <= now)
        )
        await self._session.commit()
        return result.rowcount or 0
