"""Use case : connexion d'un utilisateur (authentification par e-mail/mot de passe)."""

from dataclasses import dataclass

from src.core.exceptions import UnauthorizedError
from src.core.security import create_access_token, create_refresh_token, verify_password
from src.domain.repositories.user_repository import UserRepository


@dataclass
class LoginResultDTO:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginUserUseCase:
    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    async def execute(self, email: str, plain_password: str) -> LoginResultDTO:
        user = await self._user_repository.get_by_email(email)
        if user is None or not verify_password(plain_password, user.hashed_password):
            raise UnauthorizedError("E-mail ou mot de passe incorrect.")
        if not user.is_active:
            raise UnauthorizedError("Ce compte a été désactivé.")

        return LoginResultDTO(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )
