"""
Node : Router d'intention.

Premier node traversé à chaque tour (voir document d'architecture, §6.2).
Utilise le LLM lui-même, via un prompt système court, pour classifier l'intention
de l'utilisateur et déterminer quel agent spécialisé doit traiter la demande.

Une approche par LLM (plutôt que des règles/regex) est volontairement choisie ici :
elle généralise mieux aux formulations naturelles imprévues, typiques de l'usage vocal.
"""

from src.domain.services.llm_provider import LLMProvider
from src.infrastructure.agents.state import AgentState

ROUTER_SYSTEM_PROMPT = """Tu es un routeur d'intentions pour un assistant personnel nommé W4FO.
Analyse le dernier message de l'utilisateur et réponds UNIQUEMENT par l'un de ces mots-clés,
sans aucune explication :
- "task" si la demande concerne la création, modification, suppression ou consultation de tâches
- "calendar" si la demande concerne un rendez-vous, un événement, une réunion, ou l'agenda
- "chat" pour toute autre demande (conversation générale, questions, small talk)
"""

VALID_AGENTS = {"task", "calendar", "chat"}


async def router_node(state: AgentState, llm_provider: LLMProvider) -> AgentState:
    """Détermine l'agent spécialisé à activer pour ce tour de conversation."""
    last_user_message = next(
        (m["content"] for m in reversed(state["messages"]) if m["role"] == "user"), ""
    )

    result = await llm_provider.generate(
        messages=[
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": last_user_message},
        ]
    )

    agent_choice = result["content"].strip().lower()
    if agent_choice not in VALID_AGENTS:
        agent_choice = "chat"  # Repli sûr en cas de réponse inattendue du LLM

    state["current_agent"] = agent_choice
    return state
