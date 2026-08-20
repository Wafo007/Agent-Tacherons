"""
Registre des actions applicatives ("Action Gateway") pouvant être déclenchées
par l'agent IA sur l'interface Flutter.

Distinction volontaire avec `infrastructure/agents/tools/` (Task/Calendar) :
ces outils-là modifient des données via un repository. Une ACTION ici ne fait
JAMAIS d'accès système, de shell, ni d'exécution de code : elle produit
uniquement une INSTRUCTION structurée et strictement whitelistée, à
destination du client Flutter (ex. "navigue vers l'écran Tâches"). Le serveur
ne "clique" jamais lui-même dans l'app : il transmet une intention validée,
que Flutter est seul à exécuter (voir `VoiceChatNotifier._handleClientAction`
côté client), et seulement si le code d'action fait partie de sa propre
liste blanche de routes connues.

Flux complet (§ ACTION GATEWAY du brief) :

    AI (tool call `app_navigate`)
        → ToolRegistry (infrastructure/agents/tools/registry.py)
        → app_tools.py (adaptateur function-calling → ActionRegistry)
        → ActionRegistry.dispatch()          [ce fichier]
              → validation (code d'action + payload contre le schéma déclaré)
              → "exécution" (aucun effet de bord serveur : construction du
                résultat structuré uniquement)
        → ActionResult renvoyé au LLM comme observation (§ Feature → Result → AI)
        → en parallèle, le payload `client_action` remonte via `AgentState`,
          puis l'API REST / le WebSocket, jusqu'à Flutter, qui exécute la
          navigation réelle.
"""

from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class ActionResult:
    success: bool
    action: str
    payload: dict[str, Any]
    error: Optional[str] = None


@dataclass(frozen=True)
class ActionSpec:
    """Une action explicitement enregistrée, avec son propre validateur de payload."""

    code: str  # ex: "OPEN_TASKS" — DOIT correspondre à une route Flutter réelle et existante
    description: str
    validate: Callable[[dict[str, Any]], None]  # lève ValueError si le payload est invalide


class ActionRegistry:
    """
    Registre strict des actions applicatives disponibles pour l'agent.

    Garanties de sécurité (§ SÉCURITÉ du brief) :
    - PAS d'exécution de code arbitraire, PAS d'accès shell, PAS d'accès fichier.
    - PAS de route dynamique construite depuis une chaîne libre fournie par le LLM :
      seuls les codes explicitement `register()`-és ici peuvent être déclenchés.
    - `dispatch()` sur un code non enregistré retourne un échec structuré, ne lève
      jamais d'exception non gérée (cohérent avec la gestion d'erreurs des tools).
    """

    def __init__(self) -> None:
        self._actions: dict[str, ActionSpec] = {}

    def register(self, spec: ActionSpec) -> None:
        if spec.code in self._actions:
            raise ValueError(f"Action déjà enregistrée : {spec.code}")
        self._actions[spec.code] = spec

    def register_many(self, specs: list[ActionSpec]) -> None:
        for spec in specs:
            self.register(spec)

    def is_registered(self, code: str) -> bool:
        return code in self._actions

    def codes(self) -> list[str]:
        return list(self._actions.keys())

    def dispatch(self, code: str, payload: Optional[dict[str, Any]] = None) -> ActionResult:
        """Valide puis "exécute" (= construit le résultat structuré) une action déclarée."""
        payload = payload or {}

        if not self.is_registered(code):
            return ActionResult(success=False, action=code, payload=payload, error=f"Action inconnue : {code}")

        spec = self._actions[code]
        try:
            spec.validate(payload)
        except ValueError as exc:
            return ActionResult(success=False, action=code, payload=payload, error=str(exc))

        return ActionResult(success=True, action=code, payload=payload)


def _no_payload(payload: dict[str, Any]) -> None:
    """Validateur pour les actions de navigation simple, qui n'attendent aucun paramètre."""
    if payload:
        raise ValueError("Cette action n'accepte aucun paramètre.")


def build_default_action_registry() -> ActionRegistry:
    """
    Construit le registre des actions applicatives actuellement supportées.

    Limité STRICTEMENT aux écrans réellement existants dans l'app Flutter
    (voir `w4fo_app/lib/core/router/app_router.dart` : home, tasks, calendar,
    settings — les 4 routes de la `ShellRoute` principale). Conformément à
    l'audit préalable, on n'ajoute PAS d'actions correspondant à des écrans
    qui n'existent pas encore (ex. détail de tâche, écran mémoire) : elles
    pourront être ajoutées ici, une par une, le jour où ces écrans existeront
    — sans toucher au reste de la chaîne (agent, WebSocket, etc.).
    """
    registry = ActionRegistry()
    registry.register_many(
        [
            ActionSpec(
                code="OPEN_HOME",
                description="Ouvre l'écran principal (assistant vocal).",
                validate=_no_payload,
            ),
            ActionSpec(
                code="OPEN_TASKS",
                description="Ouvre l'écran des tâches.",
                validate=_no_payload,
            ),
            ActionSpec(
                code="OPEN_CALENDAR",
                description="Ouvre l'écran de l'agenda.",
                validate=_no_payload,
            ),
            ActionSpec(
                code="OPEN_SETTINGS",
                description="Ouvre l'écran des paramètres.",
                validate=_no_payload,
            ),
        ]
    )
    return registry
