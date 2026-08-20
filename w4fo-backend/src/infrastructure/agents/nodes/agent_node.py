"""
Node : Agent unifié (boucle agentique multi-outils).

Remplace le routage rigide V1 ("router" → un agent de domaine par tour, un
seul outil exécuté par tour) par une unique boucle de raisonnement : à
chaque itération, l'agent reçoit l'INTÉGRALITÉ du registre d'outils
disponibles (tâches + agenda, et tout domaine ajouté ultérieurement) et peut
proposer PLUSIEURS appels d'outils dans le même tour. Les résultats
(observations) sont réinjectés dans l'historique par `execute_tools_node`,
puis cet agent est rappelé pour décider de la suite (nouveaux outils, ou
réponse finale) — jusqu'à `max_iterations`.

Boucle implémentée (correspond au schéma "AGENT LOOP") :

    USER INPUT → AGENT → TOOL CALL(S) → TOOL RESULT → AGENT → ... → FINAL RESPONSE

Ce node ne fait qu'une chose : DÉCIDER (proposer des tool calls, ou répondre).
Toute l'exécution (avec gestion des erreurs et de la confirmation) est
déléguée à `execute_tools_node`, dans le même fichier.
"""

import json
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from src.core.config import get_settings
from src.domain.services.llm_provider import LLMProvider
from src.infrastructure.agents.state import AgentState
from src.infrastructure.agents.tools.registry import ToolRegistry

AGENT_SYSTEM_PROMPT = """Tu es W4FO, un assistant personnel intelligent, chaleureux et concis.
Tu peux gérer les tâches et l'agenda de l'utilisateur, et faire naviguer l'application vers un
écran (tâches, agenda, paramètres, écran principal) en utilisant les outils à ta disposition.
Utilise l'outil de navigation quand l'utilisateur demande explicitement d'afficher, d'ouvrir ou
d'aller voir un de ces écrans (ex: "montre-moi mes tâches", "va dans mon agenda").
Tu peux enchaîner PLUSIEURS outils, sur plusieurs tours de raisonnement si nécessaire, pour
répondre complètement à une demande qui combine plusieurs actions (par exemple : "organise ma
journée de demain et crée une tâche pour appeler Paul à 18h" nécessite de consulter l'agenda ET
de créer une tâche). N'hésite pas à consulter (lister) avant d'agir si cela t'aide à répondre
correctement (ex: vérifier les événements existants avant d'en créer un nouveau, ou utiliser
task_list pour retrouver le task_id exact d'une tâche mentionnée par l'utilisateur avant de la
modifier ou de la supprimer).

Nous sommes actuellement : {current_datetime}. Utilise CETTE date/heure réelle (jamais une
estimation) comme référence pour calculer toute expression temporelle relative ("demain",
"après-demain", "vendredi prochain", "dans 2 heures"...), et transmets aux outils une date déjà
calculée au format ISO 8601 (ex: "2026-08-23T18:00:00") plutôt que l'expression brute.

Une fois toutes les actions nécessaires effectuées, réponds à l'utilisateur en français, de
manière naturelle, concise et adaptée à une restitution vocale (phrases courtes, pas de listes à
puces sauf si explicitement demandé). Si un outil a échoué, informe clairement l'utilisateur de
ce qui n'a pas fonctionné plutôt que d'inventer un résultat.
{memory_context}
"""

_FR_WEEKDAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
_FR_MONTHS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def _format_current_datetime() -> str:
    """
    Date/heure actuelles réelles, dans le fuseau applicatif (`settings.app_timezone`),
    formatées en français lisible ET en ISO 8601 (les deux, pour que le LLM puisse
    s'ancrer dessus sans ambiguïté). Noms de jour/mois codés en dur (pas de dépendance
    à la locale système, potentiellement absente selon l'environnement de déploiement).
    """
    now = datetime.now(ZoneInfo(get_settings().app_timezone))
    weekday = _FR_WEEKDAYS[now.weekday()]
    month = _FR_MONTHS[now.month - 1]
    readable = f"{weekday} {now.day} {month} {now.year} à {now.strftime('%H:%M')}"
    return f"{readable} (ISO: {now.isoformat()}, fuseau: {get_settings().app_timezone})"


def _build_memory_context(memories: list[str]) -> str:
    if not memories:
        return ""
    bullet_list = "\n".join(f"- {m}" for m in memories)
    return f"\nVoici ce que tu sais déjà sur cet utilisateur :\n{bullet_list}\n"


def _parse_arguments(raw_arguments: object) -> dict:
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if isinstance(raw_arguments, str) and raw_arguments:
        try:
            return json.loads(raw_arguments)
        except json.JSONDecodeError:
            return {}
    return {}


def _observation_message(tool_call: dict, observation: dict) -> dict:
    """Construit le message 'tool' réinjecté dans l'historique pour le prochain appel LLM."""
    return {
        "role": "tool",
        "name": tool_call.get("name"),
        "tool_call_id": tool_call.get("id"),
        "content": json.dumps(observation, ensure_ascii=False, default=str),
    }


async def agent_node(state: AgentState, llm_provider: LLMProvider, tool_registry: ToolRegistry) -> AgentState:
    """
    Un tour de raisonnement de l'agent : propose 0..N appels d'outils, ou une réponse finale.

    Ce node ne modifie jamais lui-même les données applicatives : il se contente de décider.
    """
    state["iteration_count"] = state.get("iteration_count", 0) + 1
    max_iterations = state.get("max_iterations") or 6

    memory_context = _build_memory_context(state.get("relevant_memories", []))
    system_prompt = AGENT_SYSTEM_PROMPT.format(
        memory_context=memory_context, current_datetime=_format_current_datetime()
    )
    messages = [{"role": "system", "content": system_prompt}, *state["messages"]]

    if state["iteration_count"] > max_iterations:
        # Garde-fou anti-boucle infinie : nombre maximal d'itérations atteint,
        # on force une réponse finale sans proposer de nouvel outil.
        result = await llm_provider.generate(messages=messages)
        final_text = result["content"] or (
            "Je n'ai pas pu terminer cette demande dans le nombre d'étapes autorisé, "
            "peux-tu la reformuler plus simplement ?"
        )
        state["final_response"] = final_text
        state["messages"].append({"role": "assistant", "content": final_text})
        state["pending_tool_calls"] = []
        return state

    result = await llm_provider.generate(messages=messages, tools=tool_registry.definitions())

    if result["tool_calls"]:
        state["pending_tool_calls"] = result["tool_calls"]
    else:
        state["final_response"] = result["content"]
        state["messages"].append({"role": "assistant", "content": result["content"]})
        state["pending_tool_calls"] = []

    return state


async def execute_tools_node(state: AgentState, tool_registry: ToolRegistry) -> AgentState:
    """
    Exécute, dans l'ordre, tous les appels d'outils proposés par l'agent lors
    de la dernière itération.

    - Une erreur d'outil ne fait jamais planter l'agent : elle est convertie
      en observation structurée `{"success": False, "error": ..., "tool": ...}`
      par `ToolRegistry.execute`, et réinjectée dans la conversation ; l'agent
      (rappelé au tour suivant) décide alors quoi faire.
    - Si un outil SENSIBLE est rencontré, l'exécution s'arrête AVANT de
      l'exécuter : `requires_confirmation` est levé et le graphe se termine
      (voir `graph_builder.py`), en attendant la confirmation explicite de
      l'utilisateur. Les outils non sensibles déjà exécutés avant lui dans le
      même tour restent acquis.
    - Chaque exécution est ajoutée à `tool_trace` (traçabilité).
    """
    user_id = UUID(state["user_id"])
    pending = state.get("pending_tool_calls") or []

    for tool_call in pending:
        name = tool_call.get("name")

        if tool_registry.is_registered(name) and tool_registry.is_sensitive(name):
            state["pending_tool_calls"] = []
            state["pending_tool_call"] = tool_call
            state["requires_confirmation"] = True
            return state

        arguments = _parse_arguments(tool_call.get("arguments"))
        observation = await tool_registry.execute(name, arguments=arguments, user_id=user_id)

        state["tool_trace"].append({"tool": name, "arguments": arguments, "result": observation})
        state["messages"].append(_observation_message(tool_call, observation))

        client_action = observation.get("client_action") if isinstance(observation, dict) else None
        if client_action:
            state["client_actions"].append(client_action)

    state["pending_tool_calls"] = []
    state["requires_confirmation"] = False
    state["pending_tool_call"] = None
    return state
