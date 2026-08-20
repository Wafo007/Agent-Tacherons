"""
État partagé (State) du graphe LangGraph.

Cet objet transite entre tous les nodes du graphe. Il contient tout le
contexte nécessaire à la boucle agentique : historique des messages,
identifiant utilisateur, appels d'outils en attente d'exécution ou de
confirmation, trace des outils déjà exécutés dans le tour, et compteur
d'itérations (garde-fou anti-boucle infinie).

Évolution V1 → V2 (agent multi-outils) :
- `current_agent` (routage rigide vers UN agent de domaine) est supprimé :
  il n'y a plus qu'un seul agent, qui voit TOUS les outils disponibles.
- `pending_tool_call` (un seul outil) devient `pending_tool_calls` (une liste),
  pour permettre à l'agent de proposer plusieurs outils dans le même tour.
  `pending_tool_call` (singulier) est conservé pour compatibilité descendante
  avec l'API existante (`MessageResponse.pending_tool_call`, WebSocket) : il
  contient l'outil sensible qui bloque sur confirmation, le cas échéant.
- `iteration_count` / `max_iterations` implémentent la limite d'itérations
  demandée pour la boucle agentique.
- `tool_trace` rend chaque appel d'outil traçable sur toute la durée du tour.
"""

from typing import Annotated, Any, Optional

from typing_extensions import TypedDict


def add_messages(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Réducteur LangGraph : accumule les messages plutôt que de les écraser."""
    return left + right


class AgentState(TypedDict):
    """État partagé de la boucle agentique W4FO."""

    # Identité et contexte utilisateur
    user_id: str

    # Historique de conversation au format Mistral (role/content), incluant
    # les messages "tool" (observations) injectés pendant la boucle agentique.
    messages: Annotated[list[dict[str, Any]], add_messages]

    # Appels d'outils proposés par l'agent lors de la dernière itération,
    # pas encore exécutés (traités par execute_tools_node).
    pending_tool_calls: list[dict[str, Any]]

    # Compatibilité descendante : l'unique outil sensible en attente de
    # confirmation utilisateur (l'API et le WebSocket exposent ce champ).
    pending_tool_call: Optional[dict[str, Any]]

    # True si l'outil en attente nécessite une confirmation explicite de l'utilisateur
    requires_confirmation: bool

    # Réponse finale à renvoyer à l'utilisateur pour ce tour
    final_response: Optional[str]

    # Souvenirs pertinents chargés en début de tour, injectés dans le contexte de l'agent
    relevant_memories: list[str]

    # --- Boucle agentique multi-outils ---

    # Nombre d'itérations agent->outils déjà effectuées dans ce tour (garde-fou anti-boucle infinie)
    iteration_count: int

    # Nombre maximal d'itérations autorisées avant de forcer une réponse finale (configurable)
    max_iterations: int

    # Trace complète, ordonnée, de tous les outils exécutés durant ce tour
    # (nom, arguments, résultat structuré) — pour l'observabilité et le débogage.
    tool_trace: list[dict[str, Any]]

    # Actions applicatives (navigation Flutter) déclenchées durant ce tour,
    # à relayer telles quelles au client (API REST et WebSocket) — voir
    # `infrastructure/actions/action_registry.py` et `tools/app_tools.py`.
    client_actions: list[dict[str, Any]]
