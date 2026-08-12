"""
Chiffrement symétrique des données sensibles au repos (tokens OAuth tiers).

Utilise Fernet (AES-128-CBC + HMAC, via `cryptography`), avec une clé dérivée
de `JWT_SECRET_KEY`. En production, il est recommandé d'utiliser une clé de
chiffrement dédiée (`ENCRYPTION_KEY`), distincte du secret JWT, gérée via un
secret manager plutôt qu'une variable d'environnement simple — ce module reste
volontairement simple pour le MVP V1/V2 et documente ce point d'amélioration.
"""

import base64
import hashlib

from cryptography.fernet import Fernet

from src.core.config import get_settings

settings = get_settings()


def _derive_fernet_key(secret: str) -> bytes:
    """Dérive une clé Fernet valide (32 bytes, urlsafe base64) à partir d'un secret arbitraire."""
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


_fernet = Fernet(_derive_fernet_key(settings.jwt_secret_key))


def encrypt(plain_text: str) -> str:
    """Chiffre une chaîne de caractères."""
    return _fernet.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt(cipher_text: str) -> str:
    """Déchiffre une chaîne de caractères précédemment chiffrée par `encrypt`."""
    return _fernet.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
