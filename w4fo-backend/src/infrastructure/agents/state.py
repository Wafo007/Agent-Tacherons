"""
État partagé (State) du graphe LangGraph.

Cet objet transite entre tous les nodes du graphe (voir document d'architecture, §6.2).
Il contient tout le contexte nécessaire à la boucle agentique : historique des messages,
identifiant utilisateur, agent actuellement sélectionné, et éventuelle action en attente
de confirmation (pour les actions sensibles, §6.4).
"""

from typing import Annotated, Any, Optional
from uuid import UUID

from typing_extensions import TypedDict


def add_messages(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Réducteur LangGraph : accumule les messages plutôt que de les écraser."""
    return left + right


class AgentState(TypedDict):
    """État partagé de la boucle agentique W4FO."""

    # Identité et contexte utilisateur
    user_id: str

    # Historique de conversation au format Mistral (role/content)
    messages: Annotated[list[dict[str, Any]], add_messages]

    # Routage : quel agent spécialisé traite le tour courant
    current_agent: Optional[str]

    # Dernier appel d'outil détecté, en attente d'exécution ou de confirmation
    pending_tool_call: Optional[dict[str, Any]]

    # True si l'action détectée nécessite une confirmation explicite de l'utilisateur
    requires_confirmation: bool

    # Réponse finale à renvoyer à l'utilisateur pour ce tour
    final_response: Optional[str]

    # Souvenirs pertinents chargés en début de tour (§6.5), injectés dans le contexte des agents
    relevant_memories: list[str]
