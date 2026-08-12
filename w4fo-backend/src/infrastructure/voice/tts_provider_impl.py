"""
Implémentation concrète (Adapter) de TTSProvider avec edge-tts.

Choix par défaut pour le MVP V1 : synthèse vocale via edge-tts (voix Microsoft
Edge, gratuites, bonne qualité, plusieurs voix françaises disponibles), sans
clé API à gérer. Comme pour le STT, ce choix reste swappable via l'interface
`TTSProvider` (ex. migration vers ElevenLabs pour une voix plus expressive
en V2, si le budget produit le justifie).
"""

from typing import AsyncIterator

import edge_tts

# Mapping des voix "métier" (choisies dans les paramètres utilisateur) vers les
# identifiants de voix edge-tts. Permet de ne pas exposer les détails du
# fournisseur dans le reste du code (paramètres utilisateur, §2 du document).
VOICE_MAPPING = {
    "default": "fr-FR-DeniseNeural",
    "female_fr": "fr-FR-DeniseNeural",
    "male_fr": "fr-FR-HenriNeural",
}


class EdgeTTSProvider:
    """Fournisseur TTS basé sur edge-tts."""

    async def synthesize_stream(self, text: str, voice_id: str = "default") -> AsyncIterator[bytes]:
        """Synthétise le texte en flux audio MP3, chunk par chunk."""
        voice = VOICE_MAPPING.get(voice_id, VOICE_MAPPING["default"])
        communicate = edge_tts.Communicate(text=text, voice=voice)

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]
