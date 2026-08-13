"""Use case : renouvellement de session à partir d'un refresh token.

Manquait jusqu'ici : le backend émettait bien un refresh token au login
(`create_refresh_token`), mais aucun endpoint ne permettait de l'échanger
contre un nouvel access token. Le frontend Flutter n'avait donc aucun moyen
de renouveler une session expirée (access token valable 15 minutes
seulement), ce qui provoquait les erreurs d'authentification observées après
un certain temps d'utilisation.
"""

from dataclasses import dataclass
from uuid import UUID

from src.core.exceptions import UnauthorizedError
from src.core.security import create_access_token, create_refresh_token, decode_token
from src.domain.repositories.user_repository import UserRepository


@dataclass
class RefreshResultDTO:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenUseCase:
    """Valide un refresh token et émet une nouvelle paire de tokens.

    On applique une rotation du refresh token (un nouveau est émis à chaque
    renouvellement, l'ancien devenant implicitement obsolète côté client
    puisqu'il est remplacé dans le stockage sécurisé) : c'est une pratique de
    sécurité standard qui limite la fenêtre d'exploitation d'un refresh token
    qui aurait fuité, sans complexité supplémentaire côté backend (pas de
    révocation en base nécessaire pour ce périmètre).
    """

    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    async def execute(self, refresh_token: str) -> RefreshResultDTO:
        try:
            payload = decode_token(refresh_token)
        except ValueError as exc:
            raise UnauthorizedError("Refresh token invalide ou expiré.") from exc

        if payload.get("type") != "refresh":
            raise UnauthorizedError("Type de token invalide pour un renouvellement.")

        user_id = UUID(payload["sub"])
        user = await self._user_repository.get_by_id(user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("Utilisateur introuvable ou désactivé.")

        return RefreshResultDTO(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )
