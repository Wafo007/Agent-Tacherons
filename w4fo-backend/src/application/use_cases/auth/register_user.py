"""Use case : inscription d'un nouvel utilisateur."""

from dataclasses import dataclass

from src.core.exceptions import EmailAlreadyExistsError
from src.core.security import hash_password
from src.domain.entities.user import User
from src.domain.repositories.user_repository import UserRepository


@dataclass
class RegisterUserDTO:
    email: str
    full_name: str
    plain_password: str
    timezone: str = "Europe/Paris"


class RegisterUserUseCase:
    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    async def execute(self, dto: RegisterUserDTO) -> User:
        existing = await self._user_repository.get_by_email(dto.email)
        if existing is not None:
            raise EmailAlreadyExistsError(f"Un compte existe déjà avec l'e-mail {dto.email}.")

        user = User(
            email=dto.email,
            full_name=dto.full_name,
            hashed_password=hash_password(dto.plain_password),
            timezone=dto.timezone,
        )
        return await self._user_repository.create(user)
