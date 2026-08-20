"""Schémas Pydantic (contrats d'API) pour le module Conversation."""

from typing import Any, Optional

from pydantic import BaseModel


class MessageRequest(BaseModel):
    content: str
    history: list[dict[str, Any]] = []


class MessageResponse(BaseModel):
    response: str
    requires_confirmation: bool = False
    pending_tool_call: Optional[dict[str, Any]] = None
    # Trace des outils exécutés durant ce tour (nom, arguments, résultat structuré).
    # Champ additif : les clients existants qui l'ignorent ne sont pas impactés.
    tool_trace: list[dict[str, Any]] = []
    # Actions applicatives (navigation Flutter) déclenchées durant ce tour, à
    # exécuter côté client (ex: [{"action": "OPEN_TASKS", "payload": {}}]).
    client_actions: list[dict[str, Any]] = []
