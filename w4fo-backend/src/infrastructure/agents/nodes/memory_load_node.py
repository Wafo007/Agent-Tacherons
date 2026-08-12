"""
Node : Chargement de la mémoire.

Premier node du graphe (avant le router), conformément au §6.5 du document
d'architecture : "Mémoire long terme (long-term) : lue au début de chaque
exécution du graphe". Injecte les souvenirs pertinents dans `relevant_memories`,
que chaque agent spécialisé pourra ensuite inclure dans son prompt système.
"""

from uuid import UUID

from src.application.use_cases.manage_memory.search_memories import SearchRelevantMemoriesUseCase
from src.domain.repositories.memory_repository import MemoryRepository
from src.domain.services.llm_provider import LLMProvider
from src.infrastructure.agents.state import AgentState


async def memory_load_node(
    state: AgentState, memory_repository: MemoryRepository, llm_provider: LLMProvider
) -> AgentState:
    """Charge les souvenirs sémantiquement pertinents par rapport au dernier message utilisateur."""
    last_user_message = next((m["content"] for m in reversed(state["messages"]) if m["role"] == "user"), "")

    if not last_user_message:
        state["relevant_memories"] = []
        return state

    use_case = SearchRelevantMemoriesUseCase(memory_repository, llm_provider)
    memories = await use_case.execute(user_id=UUID(state["user_id"]), query_text=last_user_message, top_k=5)

    state["relevant_memories"] = [m.content for m in memories]
    return state
