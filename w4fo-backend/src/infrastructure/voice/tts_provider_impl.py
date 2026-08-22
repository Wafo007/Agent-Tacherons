"""
Implémentation concrète (Adapter) de TTSProvider avec edge-tts.

Choix par défaut pour le MVP V1 : synthèse vocale via edge-tts (voix Microsoft
Edge, gratuites, bonne qualité, plusieurs voix françaises disponibles), sans
clé API à gérer. Comme pour le STT, ce choix reste swappable via l'interface
`TTSProvider` (ex. migration vers ElevenLabs pour une voix plus expressive
en V2, si le budget produit le justifie).

§ Texte progressif synchronisé à l'audio : edge-tts expose nativement des
événements `WordBoundary` (offset/durée exacts, en unités de 100 nanosecondes,
de chaque mot dans l'audio généré) en plus des chunks audio eux-mêmes. C'est un
mécanisme du protocole SSML de Microsoft, pas une reconstruction approximative
côté W4FO : le timing renvoyé est celui réellement utilisé par le moteur de
synthèse pour prononcer chaque mot.
"""

from typing import Any, AsyncIterator

import edge_tts

# Mapping des voix "métier" (choisies dans les paramètres utilisateur) vers les
# identifiants de voix edge-tts. Permet de ne pas exposer les détails du
# fournisseur dans le reste du code (paramètres utilisateur, §2 du document).
VOICE_MAPPING = {
    "default": "fr-FR-DeniseNeural",
    "female_fr": "fr-FR-DeniseNeural",
    "male_fr": "fr-FR-HenriNeural",
}

# edge-tts exprime les offsets/durées en unités de 100 nanosecondes (ticks .NET).
_TICKS_PER_MS = 10_000


class EdgeTTSProvider:
    """Fournisseur TTS basé sur edge-tts."""

    async def synthesize_stream(self, text: str, voice_id: str = "default") -> AsyncIterator[dict[str, Any]]:
        """Synthétise le texte en flux structuré (chunks audio MP3 + timing mot par mot)."""
        voice = VOICE_MAPPING.get(voice_id, VOICE_MAPPING["default"])
        communicate = edge_tts.Communicate(text=text, voice=voice)

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield {"type": "audio", "data": chunk["data"]}
            elif chunk["type"] == "WordBoundary":
                # `chunk["text"]` est le mot tel que prononcé ; `offset`/`duration`
                # sont en ticks de 100ns depuis le début de CETTE synthèse (donc
                # relatifs au début de l'audio qui sera joué côté client).
                yield {
                    "type": "word",
                    "text": chunk["text"],
                    "offset_ms": chunk["offset"] // _TICKS_PER_MS,
                    "duration_ms": chunk["duration"] // _TICKS_PER_MS,
                }
            # Les autres types éventuels du flux edge-tts (ex. métadonnées de
            # session) sont ignorés : seuls "audio" et "WordBoundary" sont
            # pertinents pour W4FO.
