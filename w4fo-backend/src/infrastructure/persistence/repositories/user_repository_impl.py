"""
Implémentation concrète (Adapter) de UserRepository avec SQLAlchemy/PostgreSQL.

Cette classe est la SEULE responsable de la conversion entre l'entité de domaine
User (dataclass pure) et le modèle de persistance UserModel (SQLAlchemy).
Le reste du code ne manipule jamais UserModel directement.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.user import User
from src.domain.repositories.user_repository import UserRepository
from src.infrastructure.persistence.models.user_model import UserModel


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            full_name=model.full_name,
            hashed_password=model.hashed_password,
            timezone=model.timezone,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_model(entity: User) -> UserModel:
        return UserModel(
            id=entity.id,
            email=entity.email,
            full_name=entity.full_name,
            hashed_password=entity.hashed_password,
            timezone=entity.timezone,
            is_active=entity.is_active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def create(self, user: User) -> User:
        model = self._to_model(user)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        result = await self._session.execute(select(UserModel).where(UserModel.id == user_id))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self._session.execute(select(UserModel).where(UserModel.email == email))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def update(self, user: User) -> User:
        result = await self._session.execute(select(UserModel).where(UserModel.id == user.id))
        model = result.scalar_one()
        model.email = user.email
        model.full_name = user.full_name
        model.hashed_password = user.hashed_password
        model.timezone = user.timezone
        model.is_active = user.is_active
        model.updated_at = user.updated_at
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_entity(model)
