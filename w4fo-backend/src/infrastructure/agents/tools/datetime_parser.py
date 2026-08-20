"""
Résolution robuste d'expressions temporelles pour les outils Task.

Deux couches de robustesse (§ DATE ET HEURE du brief) :

1. Le prompt système de l'agent (voir `nodes/agent_node.py`) reçoit la date et
   l'heure ACTUELLES réelles du serveur, dans le fuseau applicatif — le LLM
   peut donc calculer lui-même "demain à 18h" en ISO 8601, ancré sur une
   horloge réelle plutôt que sur une estimation issue de ses données
   d'entraînement (qui n'ont aucune notion fiable de "aujourd'hui").
2. En secours — le LLM peut occasionnellement transmettre l'expression brute
   telle quelle (ex. "demain à 18h") plutôt que de la convertir — ce module
   sait résoudre déterministiquement les expressions françaises les plus
   courantes, sans dépendre d'un nouveau paquet lourd (stdlib uniquement,
   conformément à la contrainte de stabilité/dépendances du projet).

Toute date résolue est TOUJOURS timezone-aware, dans le fuseau applicatif,
pour éviter les dates ambiguës.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta


class DateTimeParsingError(ValueError):
    """Levée quand une expression temporelle ne peut être résolue de manière fiable."""


_WEEKDAYS: dict[str, int] = {
    "lundi": 0,
    "mardi": 1,
    "mercredi": 2,
    "jeudi": 3,
    "vendredi": 4,
    "samedi": 5,
    "dimanche": 6,
}

# Expressions de jour relatif. Triées par longueur décroissante à l'usage
# (voir la boucle plus bas) pour que "après-demain" soit reconnu avant
# "demain" (qui en est une sous-chaîne).
_RELATIVE_DAYS: dict[str, int] = {
    "aujourd'hui": 0,
    "aujourdhui": 0,
    "après-demain": 2,
    "apres-demain": 2,
    "après demain": 2,
    "apres demain": 2,
    "demain": 1,
}

# N'accepte QUE les formes explicites "18h", "18h30", "18:30" — un 'h' immédiatement
# collé à un nombre, ou "HH:MM". Volontairement PAS de forme "18 h" ni de simple
# nombre isolé, pour ne jamais confondre une heure avec un autre nombre de la phrase
# (ex. "dans 2 heures" ne doit pas être lu comme "2h00").
_TIME_PATTERN = re.compile(r"\b(\d{1,2})h(\d{2})?\b|\b([01]?\d|2[0-3]):([0-5]\d)\b")

_IN_HOURS_PATTERN = re.compile(r"dans\s+(\d+)\s*heures?", re.IGNORECASE)
_IN_MINUTES_PATTERN = re.compile(r"dans\s+(\d+)\s*minutes?", re.IGNORECASE)
_IN_DAYS_PATTERN = re.compile(r"dans\s+(\d+)\s*jours?", re.IGNORECASE)

_DEFAULT_HOUR_WHEN_UNSPECIFIED = 9  # heure raisonnable par défaut si seule la date est donnée


def _extract_time_of_day(text: str) -> tuple[int, int] | None:
    match = _TIME_PATTERN.search(text)
    if not match:
        return None

    if match.group(1) is not None:
        hour, minute = int(match.group(1)), int(match.group(2) or 0)
    else:
        hour, minute = int(match.group(3)), int(match.group(4))

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise DateTimeParsingError(f"Heure invalide dans l'expression : {text!r}")
    return hour, minute


def _apply_time_of_day(base: datetime, lowered_text: str, *, default_hour: int) -> datetime:
    time_of_day = _extract_time_of_day(lowered_text)
    hour, minute = time_of_day if time_of_day else (default_hour, 0)
    return base.replace(hour=hour, minute=minute, second=0, microsecond=0)


def parse_datetime_expression(value: str, *, now: datetime) -> datetime:
    """
    Résout `value` en un datetime timezone-aware, ancré sur `now` (qui DOIT déjà
    être timezone-aware, dans le fuseau applicatif — voir `_current_reference_time`
    dans `task_tools.py`).

    Ordre de résolution :
    1. ISO 8601 strict (chemin normal : le LLM a déjà calculé la date/heure
       exacte à partir du contexte fourni dans le prompt système).
    2. Expressions françaises relatives courantes (secours) : aujourd'hui,
       demain, après-demain, jours de la semaine ("lundi", "vendredi
       prochain"), "dans N heures/minutes/jours", heure seule ("à 18h").

    Lève `DateTimeParsingError` (jamais une exception générique non
    qualifiée) si rien n'a pu être résolu de façon fiable — à charge de
    l'appelant (`task_tools.py`) de laisser cette erreur remonter comme
    résultat d'outil structuré (voir `ToolRegistry.execute`, qui convertit
    toute exception en `{"success": False, "error": ...}`).
    """
    if not value or not value.strip():
        raise DateTimeParsingError("Date/heure vide.")

    text = value.strip()

    # 1. ISO 8601 strict
    try:
        iso_value = text[:-1] + "+00:00" if text.endswith("Z") else text
        parsed = datetime.fromisoformat(iso_value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=now.tzinfo)
        return parsed.astimezone(now.tzinfo)
    except ValueError:
        pass

    # 2. Expressions relatives françaises (secours)
    lowered = text.lower()

    in_hours = _IN_HOURS_PATTERN.search(lowered)
    if in_hours:
        return now + timedelta(hours=int(in_hours.group(1)))

    in_minutes = _IN_MINUTES_PATTERN.search(lowered)
    if in_minutes:
        return now + timedelta(minutes=int(in_minutes.group(1)))

    in_days = _IN_DAYS_PATTERN.search(lowered)
    if in_days:
        base = now + timedelta(days=int(in_days.group(1)))
        return _apply_time_of_day(base, lowered, default_hour=_DEFAULT_HOUR_WHEN_UNSPECIFIED)

    day_offset = None
    for expression in sorted(_RELATIVE_DAYS, key=len, reverse=True):
        if expression in lowered:
            day_offset = _RELATIVE_DAYS[expression]
            break

    if day_offset is not None:
        base = now + timedelta(days=day_offset)
        return _apply_time_of_day(base, lowered, default_hour=_DEFAULT_HOUR_WHEN_UNSPECIFIED)

    for weekday_name, weekday_index in _WEEKDAYS.items():
        if weekday_name in lowered:
            # Toujours la PROCHAINE occurrence de ce jour, jamais aujourd'hui même si
            # on tombe dessus (comportement identique que l'expression contienne
            # "prochain" ou non — "vendredi" et "vendredi prochain" sont traités pareil,
            # ce qui reste sans ambiguïté et prévisible).
            days_ahead = (weekday_index - now.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            base = now + timedelta(days=days_ahead)
            return _apply_time_of_day(base, lowered, default_hour=_DEFAULT_HOUR_WHEN_UNSPECIFIED)

    # Heure seule ("à 18h") -> aujourd'hui si pas encore passée, sinon demain.
    time_of_day = _extract_time_of_day(lowered)
    if time_of_day:
        candidate = now.replace(hour=time_of_day[0], minute=time_of_day[1], second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    raise DateTimeParsingError(
        f"Impossible de comprendre la date/heure : {value!r}. "
        "Utilise un format ISO 8601 (ex: 2026-08-23T18:00:00) ou une expression "
        "simple comme 'demain à 18h', 'vendredi prochain', 'dans 2 heures'."
    )
