"""
Implémentation concrète (Adapter) de STTProvider avec l'API Web Speech de Google,
via la bibliothèque `SpeechRecognition` (méthode `recognize_google`).

--------------------------------------------------------------------------
POURQUOI CE CHANGEMENT (remplace l'ancienne implémentation faster-whisper)
--------------------------------------------------------------------------
faster-whisper dépend de `ctranslate2`, une bibliothèque C++ compilée qui
nécessite le Visual C++ Redistributable sous Windows. Sur certains
environnements, son DLL (`ctranslate2.dll`) échoue à se charger, ce qui rend
le projet impossible à démarrer sans installation manuelle supplémentaire.

`SpeechRecognition` est un paquet 100% Python pur (aucune extension C, aucun
DLL natif). La méthode `recognize_google()` envoie l'audio à un endpoint HTTP
non officiel de Google et retourne le texte transcrit — exactement comme un
appel `httpx`/`requests` classique.

--------------------------------------------------------------------------
COMPROMIS ASSUMÉ (choix explicite de l'utilisateur du projet)
--------------------------------------------------------------------------
Ce endpoint Google Web Speech est GRATUIT et NE NÉCESSITE AUCUNE CLÉ API,
mais il est NON OFFICIEL et NON DOCUMENTÉ par Google :
- Pas de garantie de disponibilité ni de SLA.
- Rate limiting possible sans préavis, en particulier au-delà de ~50
  requêtes/jour selon des observations empiriques de la communauté
  (aucun chiffre officiel — Google peut changer cela à tout moment).
- Ne PAS utiliser en production réelle avec des utilisateurs payants.

Migration future recommandée (§10.2 du document d'architecture, choix STT
volontairement laissé ouvert) : remplacer cette classe par un provider basé
sur l'API Whisper d'OpenAI (ou Azure Speech, Deepgram...) — un simple appel
HTTP via `httpx`, zéro dépendance native supplémentaire, avec garantie de
service. Le reste du projet (WebSocket, orchestrateur, interface STTProvider)
n'a RIEN à changer pour cette migration : il suffit d'écrire une nouvelle
classe implémentant `STTProvider` et de mettre à jour `get_stt_provider()`
dans `core/dependencies.py`.
"""

import asyncio
from typing import AsyncIterator

import speech_recognition as sr


class GoogleWebSpeechSTTProvider:
    """Fournisseur STT basé sur l'API Web Speech (gratuite, non officielle) de Google."""

    def __init__(self, sample_rate: int = 16000, sample_width: int = 2, language: str = "fr-FR") -> None:
        """
        `sample_rate`/`sample_width` doivent correspondre exactement au format audio
        envoyé par le client Flutter (voir `record` package : PCM 16 bits, 16 kHz,
        mono → sample_width=2 octets par échantillon). Contrairement à l'ancienne
        implémentation faster-whisper (qui nécessitait un conteneur audio décodable
        par ffmpeg), `sr.AudioData` accepte directement du PCM brut sans en-tête —
        ce qui correspond exactement à ce que le client envoie déjà.
        """
        self._recognizer = sr.Recognizer()
        self._sample_rate = sample_rate
        self._sample_width = sample_width
        self._language = language

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcrit un segment audio complet, de façon bloquante déportée sur un thread."""
        if not audio_bytes:
            return ""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._transcribe_sync, audio_bytes)

    def _transcribe_sync(self, audio_bytes: bytes) -> str:
        audio_data = sr.AudioData(audio_bytes, self._sample_rate, self._sample_width)
        try:
            return self._recognizer.recognize_google(audio_data, language=self._language)
        except sr.UnknownValueError:
            # Aucune parole détectée / audio inintelligible — cas normal (silence, bruit),
            # pas une erreur à remonter à l'utilisateur.
            return ""
        except sr.RequestError as exc:
            # Endpoint Google injoignable ou rate limité — voir compromis assumé ci-dessus.
            raise RuntimeError(
                "Service de reconnaissance vocale temporairement indisponible "
                "(endpoint gratuit Google Web Speech). Réessaie dans quelques instants."
            ) from exc

    async def transcribe_stream(self, audio_chunks: AsyncIterator[bytes]) -> AsyncIterator[dict]:
        """
        Bufferise les chunks audio reçus et transcrit en un seul appel à la fin du flux.

        Implémentation V1 simplifiée (identique dans son principe à l'ancienne version
        faster-whisper) : accumule tout le flux puis transcrit en une fois à la
        fermeture du flux (marquée par un chunk vide `b""`). Une vraie détection de
        silence (VAD) incrémentale reste prévue pour une V2, indépendamment du
        fournisseur STT utilisé.
        """
        buffer = bytearray()
        async for chunk in audio_chunks:
            if not chunk:
                break
            buffer.extend(chunk)

        if buffer:
            text = await self.transcribe(bytes(buffer))
            if text:
                yield {"type": "final", "text": text}
