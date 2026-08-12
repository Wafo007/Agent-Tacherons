"""
Construction du graphe LangGraph d'orchestration W4FO.

Assemble les nodes définis dans `nodes/` en un graphe d'états conforme au
diagramme du §6.2 du document d'architecture. Version V4 :

    memory_load → router → chat_agent ──────────────┐
                        └─▶ task_agent ──▶ execute_task_tool ─┤
                        └─▶ calendar_agent ──▶ execute_calendar_tool ─┤
                                                                        ▼
                                                                  memory_write → END

Toutes les branches produisant une réponse finale convergent vers
`memory_write` avant `END` (§6.5 — écriture mémoire en fin de tour). Les
branches qui s'arrêtent sur une demande de confirmation (action sensible)
court-circuitent `memory_write` : il n'y a pas encore de réponse finale à
mémoriser tant que l'action n'est pas confirmée et exécutée.
"""

from functools import partial

from langgraph.graph import END, StateGraph

from src.domain.repositories.calendar_repository import CalendarEventRepository
from src.domain.repositories.google_oauth_token_repository import GoogleOAuthTokenRepository
from src.domain.repositories.memory_repository import MemoryRepository
from src.domain.repositories.task_repository import TaskRepository
from src.domain.services.calendar_provider import CalendarProvider
from src.domain.services.llm_provider import LLMProvider
from src.infrastructure.agents.nodes.calendar_agent_node import (
    calendar_agent_node,
    execute_pending_calendar_tool_node,
)
from src.infrastructure.agents.nodes.chat_agent_node import chat_agent_node
from src.infrastructure.agents.nodes.memory_load_node import memory_load_node
from src.infrastructure.agents.nodes.memory_write_node import memory_write_node
from src.infrastructure.agents.nodes.router_node import router_node
from src.infrastructure.agents.nodes.task_agent_node import execute_pending_tool_node, task_agent_node
from src.infrastructure.agents.state import AgentState


def route_after_router(state: AgentState) -> str:
    """Détermine le prochain node en fonction de l'agent choisi par le router."""
    mapping = {"task": "task_agent", "calendar": "calendar_agent"}
    return mapping.get(state["current_agent"], "chat_agent")


def _route_after_agent(state: AgentState) -> str:
    """Générique : après un agent à tools, exécute l'outil sauf si confirmation requise."""
    if state.get("pending_tool_call") is None:
        return "memory_write"
    if state.get("requires_confirmation"):
        return END  # Le graphe s'arrête ici ; l'API renvoie une demande de confirmation au client
    return "execute_tool"


def build_agent_graph(
    llm_provider: LLMProvider,
    task_repository: TaskRepository,
    calendar_repository: CalendarEventRepository,
    calendar_provider: CalendarProvider,
    token_repository: GoogleOAuthTokenRepository,
    memory_repository: MemoryRepository,
):
    """
    Construit et compile le graphe LangGraph avec les dépendances injectées.

    Retourne un graphe compilé, prêt à être invoqué via `.ainvoke(initial_state)`.
    """
    graph = StateGraph(AgentState)

    graph.add_node(
        "memory_load", partial(memory_load_node, memory_repository=memory_repository, llm_provider=llm_provider)
    )
    graph.add_node(
        "memory_write", partial(memory_write_node, memory_repository=memory_repository, llm_provider=llm_provider)
    )
    graph.add_node("router", partial(router_node, llm_provider=llm_provider))
    graph.add_node("chat_agent", partial(chat_agent_node, llm_provider=llm_provider))

    graph.add_node("task_agent", partial(task_agent_node, llm_provider=llm_provider))
    graph.add_node(
        "execute_task_tool",
        partial(execute_pending_tool_node, task_repository=task_repository, llm_provider=llm_provider),
    )

    graph.add_node("calendar_agent", partial(calendar_agent_node, llm_provider=llm_provider))
    graph.add_node(
        "execute_calendar_tool",
        partial(
            execute_pending_calendar_tool_node,
            calendar_repository=calendar_repository,
            calendar_provider=calendar_provider,
            token_repository=token_repository,
            llm_provider=llm_provider,
        ),
    )

    graph.set_entry_point("memory_load")
    graph.add_edge("memory_load", "router")

    graph.add_conditional_edges(
        "router",
        route_after_router,
        {"chat_agent": "chat_agent", "task_agent": "task_agent", "calendar_agent": "calendar_agent"},
    )

    graph.add_conditional_edges(
        "task_agent", _route_after_agent, {"execute_tool": "execute_task_tool", "memory_write": "memory_write", END: END}
    )
    graph.add_conditional_edges(
        "calendar_agent",
        _route_after_agent,
        {"execute_tool": "execute_calendar_tool", "memory_write": "memory_write", END: END},
    )

    # Toutes les branches produisant une réponse finale convergent vers memory_write
    graph.add_edge("chat_agent", "memory_write")
    graph.add_edge("execute_task_tool", "memory_write")
    graph.add_edge("execute_calendar_tool", "memory_write")
    graph.add_edge("memory_write", END)

    return graph.compile()
