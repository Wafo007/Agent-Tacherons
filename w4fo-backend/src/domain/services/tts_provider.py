"""
Interface (Port) : TTSProvider (Text-to-Speech).

Abstrait le fournisseur de synthèse vocale, pour les mêmes raisons que STTProvider
(voir domain/services/stt_provider.py).
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator


class TTSProvider(ABC):
    """Contrat pour un fournisseur de synthèse vocale (text-to-speech)."""

    @abstractmethod
    async def synthesize_stream(self, text: str, voice_id: str = "default") -> AsyncIterator[bytes]:
        """
        Synthétise un texte en flux audio, chunk par chunk.

        Utilisé pour démarrer la lecture audio dès les premiers chunks disponibles,
        plutôt que d'attendre la synthèse complète (réduction de latence perçue,
        voir document d'architecture §10.2).
        """
        raise NotImplementedError
