"""Tests unitaires de l'entité Memory (logique métier pure, sans base de données)."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.domain.entities.memory import Memory
from src.domain.value_objects.memory_type import MemoryType


def make_memory(**overrides) -> Memory:
    defaults = {"user_id": uuid4(), "content": "Aime le café le matin", "memory_type": MemoryType.PREFERENCE}
    defaults.update(overrides)
    return Memory(**defaults)


def test_memory_requires_non_empty_content():
    with pytest.raises(ValueError):
        make_memory(content="   ")


def test_importance_score_must_be_between_0_and_1():
    with pytest.raises(ValueError):
        make_memory(importance_score=1.5)


def test_reinforce_increases_importance_capped_at_one():
    memory = make_memory(importance_score=0.9)
    memory.reinforce(0.5)
    assert memory.importance_score == 1.0


def test_conversation_summary_has_default_expiry():
    expiry = Memory.default_expiry_for(MemoryType.CONVERSATION_SUMMARY)
    assert expiry is not None
    assert expiry > datetime.utcnow() + timedelta(days=89)


def test_fact_has_no_default_expiry():
    assert Memory.default_expiry_for(MemoryType.FACT) is None


def test_is_expired():
    memory = make_memory(expires_at=datetime.utcnow() - timedelta(days=1))
    assert memory.is_expired() is True
