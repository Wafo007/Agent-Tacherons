"""
Outil (tool) exposé au LLM pour déclencher une action applicative sur
l'interface Flutter (navigation vers un écran existant).

Pont entre le function calling Mistral et l'`ActionRegistry`
(`infrastructure/actions/action_registry.py`). Ce module n'exécute lui-même
AUCUNE action : il délègue strictement à l'ActionRegistry, qui valide le code
d'action contre une liste blanche fixe.

Sécurité (§ SÉCURITÉ du brief) : ce tool ne permet QUE de choisir un écran
parmi une liste FERMÉE (`enum` du JSON Schema ci-dessous). Il est impossible
pour le LLM de faire naviguer l'app vers une route arbitraire (aucune chaîne
libre n'est jamais utilisée comme route), et a fortiori d'exécuter du shell
ou du code. Cette action n'est jamais classée comme sensible : elle ne
modifie aucune donnée utilisateur, elle change seulement l'écran affiché.
"""

from typing import Any

from src.infrastructure.actions.action_registry import ActionRegistry

# Mapping fermé "écran demandé par le LLM" -> "code d'action" enregistré dans
# l'ActionRegistry. Aucune valeur ne peut être injectée en dehors de cet enum
# (le JSON Schema `enum` ci-dessous empêche déjà Mistral de proposer autre chose,
# et ce mapping constitue une seconde barrière côté serveur).
_SCREEN_TO_ACTION_CODE: dict[str, str] = {
    "home": "OPEN_HOME",
    "tasks": "OPEN_TASKS",
    "calendar": "OPEN_CALENDAR",
    "settings": "OPEN_SETTINGS",
}

APP_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "app_navigate",
            "description": (
                "Fait naviguer l'application Flutter vers un des écrans existants. "
                "Utilise cet outil quand l'utilisateur demande explicitement d'afficher, "
                "d'ouvrir ou d'aller voir ses tâches, son agenda, ses paramètres, ou de "
                "revenir à l'écran principal (ex: \"montre-moi mes tâches\", \"affiche mes "
                "tâches\", \"va dans mon agenda\", \"montre-moi mes paramètres\")."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "screen": {
                        "type": "string",
                        "enum": list(_SCREEN_TO_ACTION_CODE.keys()),
                        "description": "Écran vers lequel naviguer.",
                    },
                },
                "required": ["screen"],
            },
        },
    },
]

# Aucune action de navigation n'est sensible : elle ne modifie aucune donnée
# et n'a aucun effet destructif ou irréversible.
SENSITIVE_APP_TOOLS: set[str] = set()


async def execute_app_tool(
    tool_name: str,
    arguments: dict[str, Any],
    action_registry: ActionRegistry,
) -> dict[str, Any]:
    """
    Exécute un outil applicatif (actuellement : `app_navigate`) via l'ActionRegistry.

    Retourne un résultat structuré incluant `client_action`, le payload
    destiné à être relayé jusqu'à Flutter (voir `nodes/agent_node.py` et
    `process_message.py`) pour déclencher la navigation réelle côté client.
    """
    if tool_name != "app_navigate":
        raise ValueError(f"Outil inconnu : {tool_name}")

    screen = arguments.get("screen")
    action_code = _SCREEN_TO_ACTION_CODE.get(screen)
    if action_code is None:
        return {"success": False, "error": f"Écran inconnu ou non pris en charge : {screen}"}

    result = action_registry.dispatch(action_code, payload={})

    if not result.success:
        return {"success": False, "error": result.error}

    return {
        "success": True,
        "screen": screen,
        # Consommé par `execute_tools_node` pour alimenter `state["client_actions"]`,
        # puis remonté jusqu'à Flutter via l'API REST / le WebSocket.
        "client_action": {"action": result.action, "payload": result.payload},
    }
