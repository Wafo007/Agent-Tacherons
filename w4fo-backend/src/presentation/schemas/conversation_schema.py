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
