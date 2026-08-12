"""Use case : finalise la connexion Google Calendar après le retour du flow OAuth."""

from src.domain.entities.google_oauth_token import GoogleOAuthToken
from src.domain.repositories.google_oauth_token_repository import GoogleOAuthTokenRepository
from src.infrastructure.external_apis.google_oauth_client import compute_expiry, exchange_authorization_code


class ConnectGoogleCalendarUseCase:
    """Échange le code d'autorisation OAuth contre des tokens, et les persiste chiffrés."""

    def __init__(self, token_repository: GoogleOAuthTokenRepository) -> None:
        self._token_repository = token_repository

    async def execute(self, user_id, authorization_code: str) -> GoogleOAuthToken:
        token_data = await exchange_authorization_code(authorization_code)

        token = GoogleOAuthToken(
            user_id=user_id,
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token", ""),
            expires_at=compute_expiry(token_data.get("expires_in", 3600)),
            scopes=token_data.get("scope", "").split(" "),
        )
        return await self._token_repository.upsert(token)
