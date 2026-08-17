"""
Module de sécurité : hashing de mots de passe et gestion des tokens JWT.

Centralise toute la logique cryptographique pour éviter qu'elle ne soit
dispersée (et potentiellement mal implémentée) dans plusieurs endroits du code.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

import bcrypt
from jose import JWTError, jwt

from src.core.config import get_settings

settings = get_settings()

# --- Hashing des mots de passe ---
#
# On utilise directement le package `bcrypt` plutôt que `passlib` :
# passlib 1.7.4 (dernière version publiée, non maintenue depuis 2020) est
# incompatible avec les versions récentes de `bcrypt` (>=4.1), qui ont retiré
# l'attribut `__about__` que passlib essaie de lire pour détecter la version
# du backend. Résultat : `AttributeError: module 'bcrypt' has no attribute
# '__about__'`, suivi d'un `ValueError: password cannot be longer than 72
# bytes` car passlib retombe alors sur un mode de compatibilité cassé.
#
# bcrypt limite nativement les mots de passe à 72 bytes (limite de l'algo
# lui-même, pas de ce code) : on tronque explicitement pour éviter que
# bcrypt.hashpw ne lève une exception sur un mot de passe trop long.
_BCRYPT_MAX_BYTES = 72


def hash_password(plain_password: str) -> str:
    """Hash un mot de passe en clair avec bcrypt."""
    password_bytes = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie qu'un mot de passe en clair correspond au hash stocké."""
    password_bytes = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    try:
        return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
    except ValueError:
        # Hash mal formé / corrompu en base : on refuse plutôt que de planter.
        return False


def create_access_token(user_id: UUID, extra_claims: Optional[dict[str, Any]] = None) -> str:
    """Crée un access token JWT de courte durée."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {"sub": str(user_id), "exp": expire, "type": "access"}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: UUID) -> str:
    """Crée un refresh token JWT de longue durée."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    payload = {"sub": str(user_id), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Décode et valide un token JWT. Lève JWTError si invalide ou expiré."""
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Token invalide ou expiré.") from exc
