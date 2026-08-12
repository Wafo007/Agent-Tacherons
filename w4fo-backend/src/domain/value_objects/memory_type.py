"""Value Object : MemoryType — catégorise les souvenirs mémorisés (§7.2 du document d'architecture)."""

from enum import Enum


class MemoryType(str, Enum):
    FACT = "fact"
    PREFERENCE = "preference"
    HABIT = "habit"
    GOAL = "goal"
    CONVERSATION_SUMMARY = "conversation_summary"
