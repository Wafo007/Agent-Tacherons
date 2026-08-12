"""Tests unitaires de l'entité CalendarEvent (logique métier pure, sans base de données)."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.domain.entities.calendar_event import CalendarEvent


def make_event(**overrides) -> CalendarEvent:
    now = datetime.utcnow()
    defaults = {
        "user_id": uuid4(),
        "title": "Réunion client",
        "start_time": now,
        "end_time": now + timedelta(hours=1),
    }
    defaults.update(overrides)
    return CalendarEvent(**defaults)


def test_event_requires_non_empty_title():
    with pytest.raises(ValueError):
        make_event(title="")


def test_end_time_must_be_after_start_time():
    now = datetime.utcnow()
    with pytest.raises(ValueError):
        make_event(start_time=now, end_time=now - timedelta(hours=1))


def test_overlapping_events_detected():
    now = datetime.utcnow()
    e1 = make_event(start_time=now, end_time=now + timedelta(hours=1))
    e2 = make_event(start_time=now + timedelta(minutes=30), end_time=now + timedelta(hours=2))
    assert e1.overlaps_with(e2) is True
    assert e2.overlaps_with(e1) is True


def test_non_overlapping_events_not_detected():
    now = datetime.utcnow()
    e1 = make_event(start_time=now, end_time=now + timedelta(hours=1))
    e2 = make_event(start_time=now + timedelta(hours=2), end_time=now + timedelta(hours=3))
    assert e1.overlaps_with(e2) is False


def test_reschedule_resets_synced_flag():
    event = make_event()
    event.mark_synced("google-event-id-123")
    assert event.synced is True

    new_start = datetime.utcnow() + timedelta(days=1)
    event.reschedule(new_start, new_start + timedelta(hours=1))
    assert event.synced is False  # Nécessite une re-synchronisation
