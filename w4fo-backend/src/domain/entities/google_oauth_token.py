"""
Entité de domaine : GoogleOAuthToken.

Représente les tokens OAuth Google d'un utilisateur (Calendar, et Gmail en V3).
Le chiffrement au repos (§11 du document d'architecture) est appliqué au niveau
de l'infrastructure (voir `infrastructure/persistence/repositories/
google_oauth_token_repository_impl.py`), pas dans cette entité qui ne manipule
que des valeurs en clair une fois déchiffrées.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class GoogleOAuthToken:
    """Tokens OAuth Google associés à un utilisateur."""

    user_id: UUID
    access_token: str
    refresh_token: str
    expires_at: datetime
    scopes: list[str] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def is_expired(self, reference_time: datetime | None = None) -> bool:
        """Indique si l'access token doit être rafraîchi."""
        reference = reference_time or datetime.utcnow()
        return self.expires_at <= reference

    def refresh(self, new_access_token: str, new_expires_at: datetime) -> None:
        """Met à jour l'access token après un rafraîchissement OAuth."""
        self.access_token = new_access_token
        self.expires_at = new_expires_at
        self.updated_at = datetime.utcnow()
