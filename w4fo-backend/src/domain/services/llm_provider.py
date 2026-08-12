"""
Interface (Port) : LLMProvider.

Abstrait le fournisseur de modèle de langage. Le domaine et l'application
manipulent cette interface, jamais directement le SDK Mistral. Cela permet :
- de remplacer Mistral par un autre fournisseur sans impacter la logique métier ;
- de mettre en place un fallback en cas d'indisponibilité (voir risques, §13).
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Optional


class LLMProvider(ABC):
    """Contrat pour un fournisseur de LLM générant des réponses (avec tool calling)."""

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """Génère une réponse complète (non streamée), avec tool calling optionnel."""
        raise NotImplementedError

    @abstractmethod
    async def generate_stream(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> AsyncIterator[str]:
        """Génère une réponse en streaming (token par token) pour l'usage vocal temps réel."""
        raise NotImplementedError

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Calcule l'embedding vectoriel d'un texte (pour la mémoire sémantique)."""
        raise NotImplementedError
