"""Use case : traiter un message utilisateur à travers le graphe d'agents LangGraph."""

from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

from src.core.config import get_settings
from src.domain.repositories.calendar_repository import CalendarEventRepository
from src.domain.repositories.google_oauth_token_repository import GoogleOAuthTokenRepository
from src.domain.repositories.memory_repository import MemoryRepository
from src.domain.repositories.task_repository import TaskRepository
from src.domain.services.calendar_provider import CalendarProvider
from src.domain.services.llm_provider import LLMProvider
from src.infrastructure.agents.graph_builder import build_agent_graph
from src.infrastructure.agents.tools.tool_registry_factory import build_tool_registry


@dataclass
class ProcessMessageResultDTO:
    response: str
    requires_confirmation: bool = False
    pending_tool_call: Optional[dict[str, Any]] = None
    # Trace ordonnée de tous les outils exécutés durant ce tour (nom, arguments, résultat).
    # Champ additif, optionnel côté API : ne casse pas les clients existants.
    tool_trace: list[dict[str, Any]] = field(default_factory=list)
    # Actions applicatives (navigation Flutter) déclenchées durant ce tour.
    client_actions: list[dict[str, Any]] = field(default_factory=list)


class ProcessConversationMessageUseCase:
    """
    Orchestre le traitement d'un message utilisateur : assemble le registre
    d'outils disponibles, construit le graphe agentique, l'invoque avec
    l'historique fourni, et retourne la réponse finale (ou une demande de
    confirmation si une action sensible a été détectée en cours de route).

    Un même message peut désormais déclencher PLUSIEURS outils, y compris de
    domaines différents (tâches + agenda), enchaînés sur plusieurs itérations
    (voir `graph_builder.py` et `nodes/agent_node.py`).
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        task_repository: TaskRepository,
        calendar_repository: CalendarEventRepository,
        calendar_provider: CalendarProvider,
        token_repository: GoogleOAuthTokenRepository,
        memory_repository: MemoryRepository,
    ) -> None:
        self._llm_provider = llm_provider
        self._task_repository = task_repository
        self._calendar_repository = calendar_repository
        self._calendar_provider = calendar_provider
        self._token_repository = token_repository
        self._memory_repository = memory_repository

    async def execute(
        self,
        user_id: UUID,
        message: str,
        history: Optional[list[dict[str, Any]]] = None,
    ) -> ProcessMessageResultDTO:
        tool_registry = build_tool_registry(
            self._task_repository,
            self._calendar_repository,
            self._calendar_provider,
            self._token_repository,
        )

        graph = build_agent_graph(self._llm_provider, tool_registry, self._memory_repository)

        settings = get_settings()

        initial_state = {
            "user_id": str(user_id),
            "messages": (history or []) + [{"role": "user", "content": message}],
            "pending_tool_calls": [],
            "pending_tool_call": None,
            "requires_confirmation": False,
            "final_response": None,
            "relevant_memories": [],
            "iteration_count": 0,
            "max_iterations": settings.agent_max_iterations,
            "tool_trace": [],
            "client_actions": [],
        }

        final_state = await graph.ainvoke(initial_state)

        if final_state.get("requires_confirmation"):
            tool_call = final_state["pending_tool_call"]
            return ProcessMessageResultDTO(
                response=(
                    f"Confirmes-tu l'action « {tool_call['name']} » ? "
                    "Cette action est sensible et nécessite ta validation."
                ),
                requires_confirmation=True,
                pending_tool_call=tool_call,
                tool_trace=final_state.get("tool_trace", []),
                client_actions=final_state.get("client_actions", []),
            )

        return ProcessMessageResultDTO(
            response=final_state.get("final_response") or "",
            tool_trace=final_state.get("tool_trace", []),
            client_actions=final_state.get("client_actions", []),
        )
