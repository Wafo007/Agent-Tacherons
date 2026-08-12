"""
Tests unitaires de l'entité Task.

Ces tests ne touchent ni base de données, ni FastAPI : ils valident uniquement
la logique métier pure, ce qui est possible grâce à la Clean Architecture.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.domain.entities.task import Task
from src.domain.value_objects.priority import Priority, TaskStatus


def make_task(**overrides) -> Task:
    defaults = {"user_id": uuid4(), "title": "Préparer la présentation"}
    defaults.update(overrides)
    return Task(**defaults)


def test_task_creation_requires_a_title():
    with pytest.raises(ValueError):
        make_task(title="   ")


def test_mark_done_updates_status():
    task = make_task()
    task.mark_done()
    assert task.status == TaskStatus.DONE


def test_postpone_changes_due_date_and_status():
    task = make_task()
    new_date = datetime.utcnow() + timedelta(days=3)
    task.postpone(new_date)
    assert task.due_date == new_date
    assert task.status == TaskStatus.POSTPONED


def test_cannot_postpone_a_done_task():
    task = make_task()
    task.mark_done()
    with pytest.raises(ValueError):
        task.postpone(datetime.utcnow() + timedelta(days=1))


def test_is_overdue_true_when_due_date_in_past():
    task = make_task(due_date=datetime.utcnow() - timedelta(days=1))
    assert task.is_overdue() is True


def test_is_overdue_false_when_task_done():
    task = make_task(due_date=datetime.utcnow() - timedelta(days=1))
    task.mark_done()
    assert task.is_overdue() is False


def test_change_priority():
    task = make_task()
    task.change_priority(Priority.URGENT)
    assert task.priority == Priority.URGENT
