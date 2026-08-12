"""Schémas Pydantic (contrats d'API) pour le module Calendar."""

from datetime import datetime
from typing import List
from uuid import UUID

from pydantic import BaseModel, Field


class CreateEventRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    start_time: datetime
    end_time: datetime
    description: str = ""
    location: str = ""


class ConflictInfo(BaseModel):
    id: UUID
    title: str
    start_time: str


class CreateEventResponse(BaseModel):
    event_id: UUID
    conflicts: List[ConflictInfo] = []


class EventResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    description: str
    start_time: datetime
    end_time: datetime
    location: str
    synced: bool

    model_config = {"from_attributes": True}


class GoogleOAuthCallbackRequest(BaseModel):
    authorization_code: str


class GoogleConnectionStatusResponse(BaseModel):
    connected: bool
