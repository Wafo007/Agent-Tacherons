"""
Use case : consolidation de mémoire.

Résume une conversation terminée en un ou plusieurs faits mémorisables, pour
éviter d'accumuler l'historique brut indéfiniment (§13 — risque de dérive
mémoire). Destiné à être appelé par le scheduler en fin de session ou
périodiquement, jamais de façon synchrone dans la boucle de conversation
(pour ne pas ajouter de latence perçue par l'utilisateur).
"""

from typing import Any
from uuid import UUID

from src.application.use_cases.manage_memory.store_memory import StoreMemoryDTO, StoreMemoryUseCase
from src.domain.repositories.memory_repository import MemoryRepository
from src.domain.services.llm_provider import LLMProvider
from src.domain.value_objects.memory_type import MemoryType

CONSOLIDATION_PROMPT = """Tu analyses une conversation entre un utilisateur et son assistant personnel W4FO.
Extrait UNIQUEMENT les informations durables et réutilisables (faits, préférences, habitudes,
objectifs exprimés par l'utilisateur). Ignore le small talk et les détails ponctuels sans valeur
à long terme. Réponds avec une liste de phrases courtes, une par ligne, chacune formulée comme
un fait autonome et compréhensible hors contexte (ex: "Préfère les réunions le matin plutôt que
l'après-midi"). Si rien de mémorisable n'a été dit, réponds avec une ligne vide.
"""


class ConsolidateConversationMemoryUseCase:
    def __init__(self, memory_repository: MemoryRepository, llm_provider: LLMProvider) -> None:
        self._memory_repository = memory_repository
        self._llm_provider = llm_provider

    async def execute(self, user_id: UUID, conversation_messages: list[dict[str, Any]]) -> list[str]:
        transcript = "\n".join(f"{m['role']}: {m['content']}" for m in conversation_messages)

        result = await self._llm_provider.generate(
            messages=[
                {"role": "system", "content": CONSOLIDATION_PROMPT},
                {"role": "user", "content": transcript},
            ]
        )

        extracted_facts = [line.strip() for line in result["content"].split("\n") if line.strip()]

        store_use_case = StoreMemoryUseCase(self._memory_repository, self._llm_provider)
        for fact in extracted_facts:
            await store_use_case.execute(
                StoreMemoryDTO(user_id=user_id, content=fact, memory_type=MemoryType.FACT)
            )

        return extracted_facts
