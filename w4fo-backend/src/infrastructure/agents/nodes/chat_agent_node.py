"""
Node : Agent Conversationnel.

Traite les échanges de type "small talk" ou questions générales, sans appel d'outil.
Correspond à l'Agent Conversationnel du §6.3 du document d'architecture.
Intègre les souvenirs pertinents chargés par `memory_load_node` (§6.5) pour
personnaliser la réponse (préférences, habitudes, projets connus de l'utilisateur).
"""

from src.domain.services.llm_provider import LLMProvider
from src.infrastructure.agents.state import AgentState

CHAT_SYSTEM_PROMPT = """Tu es W4FO, un assistant personnel intelligent, chaleureux et concis.
Tu réponds en français, de manière naturelle et directe, adaptée à une conversation vocale
(phrases courtes, pas de listes à puces sauf si explicitement demandé).
{memory_context}
"""


def _build_memory_context(memories: list[str]) -> str:
    if not memories:
        return ""
    bullet_list = "\n".join(f"- {m}" for m in memories)
    return f"\nVoici ce que tu sais déjà sur cet utilisateur :\n{bullet_list}\n"


async def chat_agent_node(state: AgentState, llm_provider: LLMProvider) -> AgentState:
    """Génère une réponse conversationnelle simple, sans recours à un outil."""
    memory_context = _build_memory_context(state.get("relevant_memories", []))
    system_prompt = CHAT_SYSTEM_PROMPT.format(memory_context=memory_context)

    messages = [{"role": "system", "content": system_prompt}, *state["messages"]]
    result = await llm_provider.generate(messages=messages)

    state["final_response"] = result["content"]
    state["messages"].append({"role": "assistant", "content": result["content"]})
    return state
