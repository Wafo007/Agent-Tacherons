"""Use case : traiter un message utilisateur à travers le graphe d'agents LangGraph."""

from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from src.domain.repositories.calendar_repository import CalendarEventRepository
from src.domain.repositories.google_oauth_token_repository import GoogleOAuthTokenRepository
from src.domain.repositories.memory_repository import MemoryRepository
from src.domain.repositories.task_repository import TaskRepository
from src.domain.services.calendar_provider import CalendarProvider
from src.domain.services.llm_provider import LLMProvider
from src.infrastructure.agents.graph_builder import build_agent_graph


@dataclass
class ProcessMessageResultDTO:
    response: str
    requires_confirmation: bool = False
    pending_tool_call: Optional[dict[str, Any]] = None


class ProcessConversationMessageUseCase:
    """
    Orchestre le traitement d'un message utilisateur : construit le graphe,
    l'invoque avec l'historique fourni, et retourne la réponse (ou une demande
    de confirmation si une action sensible a été détectée).
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
        graph = build_agent_graph(
            self._llm_provider,
            self._task_repository,
            self._calendar_repository,
            self._calendar_provider,
            self._token_repository,
            self._memory_repository,
        )

        initial_state = {
            "user_id": str(user_id),
            "messages": (history or []) + [{"role": "user", "content": message}],
            "current_agent": None,
            "pending_tool_call": None,
            "requires_confirmation": False,
            "final_response": None,
            "relevant_memories": [],
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
            )

        return ProcessMessageResultDTO(response=final_state.get("final_response") or "")
