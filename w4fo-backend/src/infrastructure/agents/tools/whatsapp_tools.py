"""
Outil (tool) exposé au LLM pour répondre au message WhatsApp actuellement en
attente (§ CONVERSATION WhatsApp du brief).

Pont entre le function calling Mistral et l'`ActionRegistry`
(`infrastructure/actions/action_registry.py`), exactement comme
`app_tools.py` pour la navigation. Ce module n'envoie RIEN lui-même : il
délègue à l'ActionRegistry, qui valide le texte, puis produit un
`client_action` que le WebSocket relaie à Flutter. C'est Flutter/Android qui
envoie réellement la réponse WhatsApp, via l'action "Répondre" intégrée à la
notification WhatsApp elle-même (`RemoteInput`, API Android officielle) — le
serveur n'a et n'aura jamais accès aux serveurs ou au compte WhatsApp de
l'utilisateur. Voir `w4fo_app/lib/core/whatsapp/README.md` pour le détail de
ce mécanisme côté client.

§ SÉPARATION DES CONTEXTES : cet outil n'agit QUE sur le message WhatsApp
transmis pour CE tour (`AgentState["whatsapp_context"]`, injecté par
`agent_node.py` dans le prompt système) — jamais sur l'historique de
conversation Flutter, jamais sur la mémoire utilisateur permanente. Ce
contexte est transitoire : un seul tour, jamais persisté dans
`conversation_history` (voir `voice_ws.py`).

§ SENSIBILITÉ (choix de conception assumé) : cette action n'est PAS marquée
sensible (donc ne déclenche PAS de confirmation) afin de préserver le flux
mains libres explicitement demandé ("wafo dis que je suis occupé" → réponse
immédiate). C'est un compromis UX/sécurité documenté : contrairement à
`task_delete`/`calendar_delete` (réversibles en base), une réponse WhatsApp
envoyée est un message réel envoyé à un tiers, non annulable. Si ce
compromis doit être révisé, il suffit d'ajouter "whatsapp_reply" à
`SENSITIVE_APP_TOOLS`-équivalent (voir `tool_registry_factory.py`).
"""

from typing import Any

from src.infrastructure.actions.action_registry import ActionRegistry

WHATSAPP_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "whatsapp_reply",
            "description": (
                "Envoie une réponse au message WhatsApp actuellement en attente (fourni dans le "
                "contexte de ce tour : expéditeur + texte du message reçu). Utilise cet outil "
                "uniquement quand l'utilisateur demande explicitement de répondre à ce message "
                "(ex: \"dis-lui que je suis occupé\", \"réponds que j'arrive dans 10 minutes\"). "
                "Compose une réponse naturelle et polie à partir de ce que demande l'utilisateur, "
                "ne te contente jamais de recopier mot pour mot sa demande."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Le texte de la réponse à envoyer sur WhatsApp, tel quel.",
                    },
                },
                "required": ["message"],
            },
        },
    },
]

# Voir docstring de module : choix assumé de NE PAS rendre cette action sensible.
SENSITIVE_WHATSAPP_TOOLS: set[str] = set()


async def execute_whatsapp_tool(
    tool_name: str,
    arguments: dict[str, Any],
    action_registry: ActionRegistry,
) -> dict[str, Any]:
    """Exécute `whatsapp_reply` via l'ActionRegistry (voir docstring de module)."""
    if tool_name != "whatsapp_reply":
        raise ValueError(f"Outil inconnu : {tool_name}")

    message = arguments.get("message")
    result = action_registry.dispatch("WHATSAPP_REPLY", payload={"text": message})

    if not result.success:
        return {"success": False, "error": result.error}

    return {
        "success": True,
        "client_action": {"action": result.action, "payload": result.payload},
    }
