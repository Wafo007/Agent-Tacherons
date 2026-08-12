"""
Injection de dépendances FastAPI.

Ce module est le "point de câblage" de l'application : c'est ICI, et uniquement ici,
que l'on relie les interfaces du domaine à leurs implémentations concrètes
(infrastructure). Les routers ne connaissent que ces dependencies, jamais
SQLAlchemy ou les classes d'implémentation directement.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import decode_token
from src.domain.repositories.calendar_repository import CalendarEventRepository
from src.domain.repositories.google_oauth_token_repository import GoogleOAuthTokenRepository
from src.domain.repositories.memory_repository import MemoryRepository
from src.domain.repositories.notification_repository import NotificationRepository
from src.domain.repositories.task_repository import TaskRepository
from src.domain.repositories.user_repository import UserRepository
from src.domain.repositories.user_settings_repository import UserSettingsRepository
from src.domain.services.calendar_provider import CalendarProvider
from src.domain.services.llm_provider import LLMProvider
from src.domain.services.stt_provider import STTProvider
from src.domain.services.tts_provider import TTSProvider
from src.infrastructure.external_apis.google_calendar_client import GoogleCalendarProvider
from src.infrastructure.llm.mistral_provider import MistralLLMProvider
from src.infrastructure.persistence.database import get_db_session
from src.infrastructure.persistence.repositories.calendar_repository_impl import SQLAlchemyCalendarEventRepository
from src.infrastructure.persistence.repositories.google_oauth_token_repository_impl import (
    SQLAlchemyGoogleOAuthTokenRepository,
)
from src.infrastructure.persistence.repositories.memory_repository_impl import SQLAlchemyMemoryRepository
from src.infrastructure.persistence.repositories.notification_repository_impl import SQLAlchemyNotificationRepository
from src.infrastructure.persistence.repositories.task_repository_impl import SQLAlchemyTaskRepository
from src.infrastructure.persistence.repositories.user_repository_impl import SQLAlchemyUserRepository
from src.infrastructure.persistence.repositories.user_settings_repository_impl import (
    SQLAlchemyUserSettingsRepository,
)
from src.infrastructure.voice.stt_provider_impl import GoogleWebSpeechSTTProvider
from src.infrastructure.voice.tts_provider_impl import EdgeTTSProvider

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_user_repository(session: DbSession) -> UserRepository:
    return SQLAlchemyUserRepository(session)


def get_task_repository(session: DbSession) -> TaskRepository:
    return SQLAlchemyTaskRepository(session)


UserRepo = Annotated[UserRepository, Depends(get_user_repository)]
TaskRepo = Annotated[TaskRepository, Depends(get_task_repository)]


def get_calendar_repository(session: DbSession) -> CalendarEventRepository:
    return SQLAlchemyCalendarEventRepository(session)


def get_google_oauth_token_repository(session: DbSession) -> GoogleOAuthTokenRepository:
    return SQLAlchemyGoogleOAuthTokenRepository(session)


def get_calendar_provider() -> CalendarProvider:
    """Point de câblage unique pour le fournisseur d'agenda (Google Calendar en V2)."""
    return GoogleCalendarProvider()


CalendarRepo = Annotated[CalendarEventRepository, Depends(get_calendar_repository)]
GoogleTokenRepo = Annotated[GoogleOAuthTokenRepository, Depends(get_google_oauth_token_repository)]
CalendarProviderDep = Annotated[CalendarProvider, Depends(get_calendar_provider)]


def get_memory_repository(session: DbSession) -> MemoryRepository:
    return SQLAlchemyMemoryRepository(session)


MemoryRepo = Annotated[MemoryRepository, Depends(get_memory_repository)]


def get_user_settings_repository(session: DbSession) -> UserSettingsRepository:
    return SQLAlchemyUserSettingsRepository(session)


def get_notification_repository(session: DbSession) -> NotificationRepository:
    return SQLAlchemyNotificationRepository(session)


UserSettingsRepo = Annotated[UserSettingsRepository, Depends(get_user_settings_repository)]
NotificationRepo = Annotated[NotificationRepository, Depends(get_notification_repository)]


def get_llm_provider() -> LLMProvider:
    """
    Fournit l'implémentation du LLM à utiliser.

    Un seul point de câblage : passer à un autre fournisseur (ou ajouter un
    fallback) ne nécessite de modifier que cette fonction.
    """
    return MistralLLMProvider()


LLMProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]

# --- Instances singleton pour STT/TTS ---
# Instanciés une seule fois au démarrage du process plutôt qu'à chaque connexion
# WebSocket (évite une recréation inutile de l'objet Recognizer/Communicate à chaque appel).
_stt_provider_instance: STTProvider = GoogleWebSpeechSTTProvider()
_tts_provider_instance: TTSProvider = EdgeTTSProvider()


def get_stt_provider() -> STTProvider:
    return _stt_provider_instance


def get_tts_provider() -> TTSProvider:
    return _tts_provider_instance


STTProviderDep = Annotated[STTProvider, Depends(get_stt_provider)]
TTSProviderDep = Annotated[TTSProvider, Depends(get_tts_provider)]


async def get_current_user_id(token: Annotated[str, Depends(oauth2_scheme)]) -> UUID:
    """Extrait et valide l'utilisateur courant à partir du token JWT (access token)."""
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Type de token invalide.")

    return UUID(payload["sub"])


CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]


def get_current_user_id_from_token(token: str) -> UUID:
    """
    Valide un token JWT reçu en paramètre de requête et retourne l'ID utilisateur.

    Utilisé pour l'authentification WebSocket (`voice_ws.py`) : contrairement à
    une requête REST classique, un client WebSocket ne peut pas toujours envoyer
    un header Authorization au moment du handshake selon les plateformes/libs
    Flutter utilisées ; le token est donc transmis en query param (`?token=...`).
    """
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise ValueError("Token invalide ou expiré.") from exc

    if payload.get("type") != "access":
        raise ValueError("Type de token invalide.")

    return UUID(payload["sub"])
