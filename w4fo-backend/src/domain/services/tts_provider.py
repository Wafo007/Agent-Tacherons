"""
Interface (Port) : TTSProvider (Text-to-Speech).

Abstrait le fournisseur de synthèse vocale, pour les mêmes raisons que STTProvider
(voir domain/services/stt_provider.py).
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator


class TTSProvider(ABC):
    """Contrat pour un fournisseur de synthèse vocale (text-to-speech)."""

    @abstractmethod
    def synthesize_stream(self, text: str, voice_id: str = "default") -> AsyncIterator[dict[str, Any]]:
        """
        Synthétise un texte en flux de chunks structurés, chacun de la forme :

            {"type": "audio", "data": bytes}
            {"type": "word", "text": str, "offset_ms": int, "duration_ms": int}

        Les chunks `"word"` (§ affichage progressif du texte, synchronisé avec la
        lecture audio) donnent, pour chaque mot prononcé, sa position temporelle
        EXACTE dans l'audio (`offset_ms` = décalage depuis le début de la
        synthèse). C'est ce qui permet au client de révéler le texte à l'écran au
        même rythme que la voix, plutôt que d'afficher toute la réponse d'un coup
        (§10.2 du document d'architecture, complété par la fonctionnalité Wake
        Word V2).

        Un fournisseur qui ne sait pas produire de timing mot-par-mot (ex. futur
        remplacement par un moteur TTS plus simple) peut légitimement n'émettre
        que des chunks `"audio"` : le client dégrade alors proprement en
        affichant le texte complet une fois la lecture terminée, plutôt que de
        planter (voir `voice_ws.py` et `voice_chat_provider.dart`).

        Utilisé pour démarrer la lecture audio dès les premiers chunks disponibles,
        plutôt que d'attendre la synthèse complète (réduction de latence perçue).
        """
        raise NotImplementedError
