"""
Node : Agent Tâches.

Traite les demandes liées à la gestion des tâches, avec tool calling Mistral.
Correspond à l'Agent Tâches du §6.3 du document d'architecture.

Applique la classification de sensibilité (§6.4) : si l'outil détecté est sensible
(ex: task_delete), l'exécution est suspendue et `requires_confirmation` est levé
plutôt que d'exécuter l'action directement.
"""

from uuid import UUID

from src.domain.repositories.task_repository import TaskRepository
from src.domain.services.llm_provider import LLMProvider
from src.infrastructure.agents.state import AgentState
from src.infrastructure.agents.tools.task_tools import (
    SENSITIVE_TOOLS,
    TASK_TOOL_DEFINITIONS,
    execute_task_tool,
)

TASK_AGENT_SYSTEM_PROMPT = """Tu es l'agent Tâches de l'assistant W4FO.
Tu aides l'utilisateur à créer, consulter, modifier ou supprimer ses tâches
en utilisant les outils à ta disposition. Sois concis dans tes réponses,
adaptées à une restitution vocale.
"""


async def task_agent_node(state: AgentState, llm_provider: LLMProvider) -> AgentState:
    """Détermine si un outil doit être appelé et prépare son exécution (ou la confirmation requise)."""
    messages = [{"role": "system", "content": TASK_AGENT_SYSTEM_PROMPT}, *state["messages"]]
    result = await llm_provider.generate(messages=messages, tools=TASK_TOOL_DEFINITIONS)

    if result["tool_calls"]:
        tool_call = result["tool_calls"][0]  # V1 : un seul outil par tour, simplification volontaire
        state["pending_tool_call"] = tool_call
        state["requires_confirmation"] = tool_call["name"] in SENSITIVE_TOOLS
    else:
        state["final_response"] = result["content"]
        state["messages"].append({"role": "assistant", "content": result["content"]})

    return state


async def execute_pending_tool_node(
    state: AgentState,
    task_repository: TaskRepository,
    llm_provider: LLMProvider,
) -> AgentState:
    """Exécute l'outil en attente (déjà validé si sensible), puis reformule le résultat pour l'utilisateur."""
    import json

    tool_call = state["pending_tool_call"]
    assert tool_call is not None

    arguments = json.loads(tool_call["arguments"]) if isinstance(tool_call["arguments"], str) else tool_call["arguments"]
    observation = await execute_task_tool(
        tool_name=tool_call["name"],
        arguments=arguments,
        user_id=UUID(state["user_id"]),
        task_repository=task_repository,
    )

    # Réinjection du résultat de l'outil pour que le LLM formule une réponse naturelle
    messages = [
        {"role": "system", "content": TASK_AGENT_SYSTEM_PROMPT},
        *state["messages"],
        {"role": "assistant", "content": f"Résultat de l'action {tool_call['name']} : {observation}"},
    ]
    result = await llm_provider.generate(messages=messages)

    state["final_response"] = result["content"]
    state["messages"].append({"role": "assistant", "content": result["content"]})
    state["pending_tool_call"] = None
    state["requires_confirmation"] = False
    return state
