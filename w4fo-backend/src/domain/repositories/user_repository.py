"""
Interface (Port) : UserRepository.

Le domaine définit CE DONT il a besoin pour persister/récupérer des utilisateurs,
sans jamais connaître la technologie de persistance réelle (PostgreSQL, SQLAlchemy...).
C'est l'infrastructure qui implémentera cette interface (voir
infrastructure/persistence/repositories/user_repository_impl.py).
"""

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from src.domain.entities.user import User


class UserRepository(ABC):
    """Contrat de persistance pour l'entité User."""

    @abstractmethod
    async def create(self, user: User) -> User:
        """Persiste un nouvel utilisateur."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Récupère un utilisateur par son identifiant."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        """Récupère un utilisateur par son adresse e-mail."""
        raise NotImplementedError

    @abstractmethod
    async def update(self, user: User) -> User:
        """Met à jour un utilisateur existant."""
        raise NotImplementedError
