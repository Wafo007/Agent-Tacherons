"""
Node : Agent Agenda.

Traite les demandes liées à l'agenda (consultation, création, suppression),
avec tool calling Mistral. Correspond à l'Agent Agenda du §6.3 du document
d'architecture. Suit exactement le même schéma que `task_agent_node.py`
(cohérence délibérée entre agents pour faciliter la maintenance).
"""

from uuid import UUID

from src.domain.repositories.calendar_repository import CalendarEventRepository
from src.domain.repositories.google_oauth_token_repository import GoogleOAuthTokenRepository
from src.domain.services.calendar_provider import CalendarProvider
from src.domain.services.llm_provider import LLMProvider
from src.infrastructure.agents.state import AgentState
from src.infrastructure.agents.tools.calendar_tools import (
    CALENDAR_TOOL_DEFINITIONS,
    SENSITIVE_CALENDAR_TOOLS,
    execute_calendar_tool,
)

CALENDAR_AGENT_SYSTEM_PROMPT = """Tu es l'agent Agenda de l'assistant W4FO.
Tu aides l'utilisateur à consulter, créer ou supprimer des événements dans son agenda,
en utilisant les outils à ta disposition. La date et l'heure actuelles te seront données
dans le contexte si nécessaire pour interpréter des expressions comme "demain" ou "la semaine prochaine".
Sois concis, adapté à une restitution vocale. Si un conflit d'agenda est signalé dans le
résultat d'un outil, informe clairement l'utilisateur du chevauchement détecté.
"""


async def calendar_agent_node(state: AgentState, llm_provider: LLMProvider) -> AgentState:
    """Détermine si un outil Agenda doit être appelé et prépare son exécution (ou la confirmation requise)."""
    messages = [{"role": "system", "content": CALENDAR_AGENT_SYSTEM_PROMPT}, *state["messages"]]
    result = await llm_provider.generate(messages=messages, tools=CALENDAR_TOOL_DEFINITIONS)

    if result["tool_calls"]:
        tool_call = result["tool_calls"][0]  # V1 : un seul outil par tour, cohérent avec task_agent_node
        state["pending_tool_call"] = tool_call
        state["requires_confirmation"] = tool_call["name"] in SENSITIVE_CALENDAR_TOOLS
    else:
        state["final_response"] = result["content"]
        state["messages"].append({"role": "assistant", "content": result["content"]})

    return state


async def execute_pending_calendar_tool_node(
    state: AgentState,
    calendar_repository: CalendarEventRepository,
    calendar_provider: CalendarProvider,
    token_repository: GoogleOAuthTokenRepository,
    llm_provider: LLMProvider,
) -> AgentState:
    """Exécute l'outil Agenda en attente, puis reformule le résultat pour l'utilisateur."""
    import json

    tool_call = state["pending_tool_call"]
    assert tool_call is not None

    arguments = json.loads(tool_call["arguments"]) if isinstance(tool_call["arguments"], str) else tool_call["arguments"]
    observation = await execute_calendar_tool(
        tool_name=tool_call["name"],
        arguments=arguments,
        user_id=UUID(state["user_id"]),
        calendar_repository=calendar_repository,
        calendar_provider=calendar_provider,
        token_repository=token_repository,
    )

    messages = [
        {"role": "system", "content": CALENDAR_AGENT_SYSTEM_PROMPT},
        *state["messages"],
        {"role": "assistant", "content": f"Résultat de l'action {tool_call['name']} : {observation}"},
    ]
    result = await llm_provider.generate(messages=messages)

    state["final_response"] = result["content"]
    state["messages"].append({"role": "assistant", "content": result["content"]})
    state["pending_tool_call"] = None
    state["requires_confirmation"] = False
    return state
