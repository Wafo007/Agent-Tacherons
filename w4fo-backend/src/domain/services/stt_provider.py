"""
Interface (Port) : STTProvider (Speech-to-Text).

Abstrait le fournisseur de reconnaissance vocale. Le document d'architecture
(§10.2) laisse volontairement ce choix ouvert (Whisper self-hosted vs API cloud) :
cette interface permet de changer d'implémentation sans impacter le WebSocket
vocal ni l'orchestrateur d'agents.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator


class STTProvider(ABC):
    """Contrat pour un fournisseur de transcription vocale (speech-to-text)."""

    @abstractmethod
    async def transcribe_stream(self, audio_chunks: AsyncIterator[bytes]) -> AsyncIterator[dict]:
        """
        Transcrit un flux audio en streaming.

        Doit produire des événements du type :
        - {"type": "interim", "text": "..."}  → transcription partielle, affichée en live
        - {"type": "final", "text": "..."}    → transcription finale d'un segment de parole
        """
        raise NotImplementedError

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcrit un segment audio complet (non streamé) et retourne le texte final."""
        raise NotImplementedError
