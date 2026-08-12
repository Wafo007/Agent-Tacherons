"""
Implémentation concrète (Adapter) de LLMProvider avec l'API officielle Mistral AI.

C'est la SEULE classe du projet qui importe le SDK `mistralai`. Le reste du code
(use cases, agents LangGraph) ne manipule que l'interface `LLMProvider` du domaine.
Cela permet de changer de fournisseur LLM, ou d'ajouter un fallback, sans toucher
à la logique métier ni à l'orchestration des agents.
"""

from typing import Any, AsyncIterator, Optional

from mistralai import Mistral

from src.core.config import get_settings
from src.domain.services.llm_provider import LLMProvider

settings = get_settings()


class MistralLLMProvider(LLMProvider):
    """Fournisseur LLM basé sur l'API Mistral AI (chat + embeddings)."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self._client = Mistral(api_key=api_key or settings.mistral_api_key)
        self._model = model or settings.mistral_model
        self._embed_model = "mistral-embed"

    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """Génère une réponse complète, avec tool calling optionnel (function calling)."""
        response = await self._client.chat.complete_async(
            model=self._model,
            messages=messages,
            tools=tools,
            tool_choice="auto" if tools else None,
        )
        choice = response.choices[0]
        message = choice.message

        return {
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
                for tc in (message.tool_calls or [])
            ],
            "finish_reason": choice.finish_reason,
        }

    async def generate_stream(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> AsyncIterator[str]:
        """
        Génère une réponse en streaming (token par token).

        Utilisé par le flux vocal temps réel (§10 du document d'architecture) :
        permet de démarrer la synthèse vocale dès les premiers mots générés,
        sans attendre la fin de la réponse complète.
        """
        stream = await self._client.chat.stream_async(
            model=self._model,
            messages=messages,
            tools=tools,
            tool_choice="auto" if tools else None,
        )
        async for event in stream:
            delta = event.data.choices[0].delta
            if delta.content:
                yield delta.content

    async def embed(self, text: str) -> list[float]:
        """Calcule l'embedding vectoriel d'un texte via mistral-embed (pour la mémoire sémantique)."""
        response = await self._client.embeddings.create_async(model=self._embed_model, inputs=[text])
        return response.data[0].embedding
