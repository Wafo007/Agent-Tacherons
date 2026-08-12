"""
Entité de domaine : User.

Représente un utilisateur de W4FO. Cette classe est un objet métier pur :
elle ne connaît ni la base de données, ni FastAPI, ni aucun framework.
Elle porte uniquement les règles et invariants métier liés à un utilisateur.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class User:
    """Représente un utilisateur du système W4FO."""

    email: str
    full_name: str
    hashed_password: str
    timezone: str = "Europe/Paris"
    id: UUID = field(default_factory=uuid4)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def deactivate(self) -> None:
        """Désactive le compte utilisateur (soft-delete métier)."""
        self.is_active = False
        self.updated_at = datetime.utcnow()

    def rename(self, new_full_name: str) -> None:
        """Met à jour le nom complet de l'utilisateur avec validation minimale."""
        if not new_full_name or not new_full_name.strip():
            raise ValueError("Le nom complet ne peut pas être vide.")
        self.full_name = new_full_name.strip()
        self.updated_at = datetime.utcnow()
