"""
Node : Écriture de la mémoire.

Dernier node du graphe, exécuté après la génération de la réponse finale
(§6.5 du document d'architecture : "écrite à la fin de chaque exécution du
graphe"). Analyse le seul échange du tour courant (message utilisateur +
réponse assistant) — pas l'historique complet — pour limiter le coût et la
latence d'un appel LLM supplémentaire à chaque tour.

Compromis assumé (documenté au §13, risque de dérive mémoire / latence) :
cet appel s'ajoute au temps de réponse perçu par l'utilisateur puisqu'il est
synchrone dans le graphe. Une version V3 pourra le déporter en tâche de fond
(ex. `asyncio.create_task` détachée, ou job scheduler post-conversation) pour
ne plus impacter la latence vocale — non fait ici pour rester simple et éviter
les effets de bord d'une tâche détachée sur la durée de vie de la session DB.
"""

from uuid import UUID

from src.application.use_cases.manage_memory.store_memory import StoreMemoryDTO, StoreMemoryUseCase
from src.domain.repositories.memory_repository import MemoryRepository
from src.domain.services.llm_provider import LLMProvider
from src.domain.value_objects.memory_type import MemoryType
from src.infrastructure.agents.state import AgentState

MEMORY_EXTRACTION_PROMPT = """Tu analyses UN SEUL échange entre un utilisateur et son assistant W4FO.
Extrait UNIQUEMENT les informations durables et réutilisables que l'utilisateur a révélées sur
lui-même (préférence, habitude, fait personnel, objectif). Ignore tout le reste (small talk,
contenu de la réponse de l'assistant, demandes ponctuelles sans valeur à long terme comme "crée
une tâche X"). Réponds avec au maximum 2 phrases courtes, une par ligne, formulées comme des faits
autonomes (ex: "Travaille habituellement le samedi matin"). Si rien de mémorisable, réponds "RIEN".
"""


async def memory_write_node(
    state: AgentState, memory_repository: MemoryRepository, llm_provider: LLMProvider
) -> AgentState:
    """Extrait et mémorise les informations durables révélées dans le dernier échange du tour."""
    last_user_message = next((m["content"] for m in reversed(state["messages"]) if m["role"] == "user"), "")
    final_response = state.get("final_response") or ""

    if not last_user_message:
        return state

    exchange = f"Utilisateur: {last_user_message}\nAssistant: {final_response}"

    result = await llm_provider.generate(
        messages=[
            {"role": "system", "content": MEMORY_EXTRACTION_PROMPT},
            {"role": "user", "content": exchange},
        ]
    )

    extracted = result["content"].strip()
    if not extracted or extracted.upper() == "RIEN":
        return state

    store_use_case = StoreMemoryUseCase(memory_repository, llm_provider)
    for line in extracted.split("\n"):
        fact = line.strip("- ").strip()
        if fact:
            await store_use_case.execute(
                StoreMemoryDTO(user_id=UUID(state["user_id"]), content=fact, memory_type=MemoryType.FACT)
            )

    return state
