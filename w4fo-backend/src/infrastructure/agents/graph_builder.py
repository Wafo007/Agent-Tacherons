"""
Construction du graphe LangGraph d'orchestration W4FO.

Architecture V2 (agent unique multi-outils), remplaçant le routage rigide V1
("router" → un agent de domaine → un seul outil par tour) :

    memory_load → agent ──(pas d'outil)──────────────▶ memory_write → END
                     │
                     ├──(outils proposés)──▶ execute_tools ──┐
                     │                                        │
                     │        ┌───────────────────────────────┘
                     │        │
                     │        ├──(outil sensible en attente)──▶ END
                     │        │        (le client doit confirmer avant de relancer)
                     │        │
                     │        └──(outils exécutés, pas de blocage)──▶ agent (boucle)
                     │
                     ▼
              (jusqu'à `max_iterations` itérations agent↔outils)

Toutes les branches produisant une réponse finale convergent vers
`memory_write` avant `END` (écriture mémoire en fin de tour). La branche qui
s'arrête sur une demande de confirmation (action sensible) court-circuite
`memory_write` : il n'y a pas encore de réponse finale à mémoriser tant que
l'action n'est pas confirmée et exécutée.

Ce graphe permet à un seul message utilisateur de déclencher PLUSIEURS
outils, y compris de domaines différents (tâches + agenda), enchaînés en
plusieurs itérations si nécessaire — voir `nodes/agent_node.py`.
"""

from functools import partial

from langgraph.graph import END, StateGraph

from src.domain.repositories.memory_repository import MemoryRepository
from src.domain.services.llm_provider import LLMProvider
from src.infrastructure.agents.nodes.agent_node import agent_node, execute_tools_node
from src.infrastructure.agents.nodes.memory_load_node import memory_load_node
from src.infrastructure.agents.nodes.memory_write_node import memory_write_node
from src.infrastructure.agents.state import AgentState
from src.infrastructure.agents.tools.registry import ToolRegistry


def _route_after_agent(state: AgentState) -> str:
    """Après une décision de l'agent : exécuter les outils proposés, ou conclure le tour."""
    if state.get("pending_tool_calls"):
        return "execute_tools"
    return "memory_write"


def _route_after_tools(state: AgentState) -> str:
    """
    Après exécution des outils : si un outil sensible bloque sur confirmation,
    le graphe s'arrête (l'API renvoie la demande de confirmation au client).
    Sinon, on retourne à l'agent pour qu'il décide de la suite (nouvel outil,
    ou réponse finale) — c'est ce qui permet l'enchaînement multi-outils.
    """
    if state.get("requires_confirmation"):
        return END
    return "agent"


def build_agent_graph(
    llm_provider: LLMProvider,
    tool_registry: ToolRegistry,
    memory_repository: MemoryRepository,
):
    """
    Construit et compile le graphe LangGraph avec les dépendances injectées.

    `tool_registry` est déjà entièrement assemblé pour ce tour de conversation
    (voir `tools/tool_registry_factory.build_tool_registry`) : le graphe lui-même
    reste agnostique du nombre et de la nature des outils disponibles.

    Retourne un graphe compilé, prêt à être invoqué via `.ainvoke(initial_state)`.
    """
    graph = StateGraph(AgentState)

    graph.add_node(
        "memory_load", partial(memory_load_node, memory_repository=memory_repository, llm_provider=llm_provider)
    )
    graph.add_node(
        "memory_write", partial(memory_write_node, memory_repository=memory_repository, llm_provider=llm_provider)
    )
    graph.add_node("agent", partial(agent_node, llm_provider=llm_provider, tool_registry=tool_registry))
    graph.add_node("execute_tools", partial(execute_tools_node, tool_registry=tool_registry))

    graph.set_entry_point("memory_load")
    graph.add_edge("memory_load", "agent")

    graph.add_conditional_edges(
        "agent",
        _route_after_agent,
        {"execute_tools": "execute_tools", "memory_write": "memory_write"},
    )
    graph.add_conditional_edges(
        "execute_tools",
        _route_after_tools,
        {"agent": "agent", END: END},
    )

    graph.add_edge("memory_write", END)

    return graph.compile()
