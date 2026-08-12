"""
Client OAuth Google : gère l'échange du code d'autorisation contre des tokens,
et le rafraîchissement de l'access token expiré.

Distinct de `GoogleCalendarProvider` (qui appelle l'API Calendar elle-même) :
ce module ne connaît que le endpoint OAuth générique de Google, réutilisable
tel quel pour Gmail en V3 (mêmes credentials, scopes différents).
"""

from datetime import datetime, timedelta
from typing import Any

import httpx

from src.core.config import get_settings

settings = get_settings()

GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"


async def exchange_authorization_code(code: str) -> dict[str, Any]:
    """Échange un code d'autorisation OAuth contre un access token + refresh token."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        return response.json()


async def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    """Rafraîchit un access token expiré à partir du refresh token."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_ENDPOINT,
            data={
                "refresh_token": refresh_token,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        return response.json()


def compute_expiry(expires_in_seconds: int) -> datetime:
    """Calcule la date d'expiration absolue à partir de la durée de vie relative renvoyée par Google."""
    return datetime.utcnow() + timedelta(seconds=expires_in_seconds)
