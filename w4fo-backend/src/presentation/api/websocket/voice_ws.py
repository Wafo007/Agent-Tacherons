"""
Endpoint WebSocket : conversation vocale temps réel.

Implémente la séquence décrite au §10.1 du document d'architecture :

    Utilisateur → audio (chunks binaires) → STT → texte final
        → Orchestrateur LangGraph → réponse texte
        → TTS (streaming par phrase) → audio (chunks binaires) → Utilisateur

Protocole du canal (multiplexé sur une seule connexion WebSocket, §10.2) :

- Le client envoie des frames BINAIRES = chunks audio bruts (PCM/WAV).
- Le client envoie des frames TEXTE JSON pour les événements de contrôle :
    {"event": "end_of_speech"}   → signale la fin d'un segment de parole
    {"event": "end_of_speech", "whatsapp_context": {"sender": "Paul", "text": "..."}}
                                 → idem, avec le message WhatsApp en attente de réponse pour ce
                                   tour (§ CONTEXTE, séparation des contextes) — voir
                                   `whatsapp_tools.py` et `w4fo_app/lib/core/whatsapp/README.md`.
    {"event": "interrupt"}       → barge-in : annule la réception en cours OU
                                    la réponse en cours (processing/TTS), voir
                                    § BARGE-IN ci-dessous.
- Le serveur envoie des frames TEXTE JSON pour les événements de contrôle :
    {"event": "transcript", "text": "..."}
    {"event": "agent_thinking"}
    {"event": "tool_calls_summary", "tools": [{"tool": "...", "success": true}, ...]}
    {"event": "response_word", "text": "...", "offset_ms": 0, "duration_ms": 0}
    {"event": "response_text_final", "text": "..."}
    {"event": "requires_confirmation", "tool_call": {...}}
    {"event": "client_action", "action": "OPEN_TASKS", "payload": {...}}
    {"event": "command_timeout"}
    {"event": "interrupted"}
    {"event": "end_of_turn"}
- Le serveur envoie des frames BINAIRES = chunks audio de la réponse (MP3).

§ TEXTE PROGRESSIF (synchronisé à l'audio, pas "plaqué" d'un coup) :
`response_word` est émis un par un, avec le timing EXACT (offset/durée en
millisecondes depuis le début de CETTE réponse) auquel edge-tts prononce ce
mot dans l'audio (voir `EdgeTTSProvider`). Le client programme l'affichage de
chaque mot à `offset_ms` après le DÉBUT de la lecture audio (pas à la
réception réseau du message, qui est sujette à la gigue) — voir
`voice_chat_provider.dart`. `response_text_final` porte le texte complet, émis
juste avant `end_of_turn`, uniquement pour réconcilier l'historique de
conversation (jamais affiché d'un bloc avant/à la place de l'affichage
progressif).

§ BARGE-IN (interruption pendant la réponse) :
Le protocole WebSocket ne permet qu'un seul lecteur (`receive()`) actif à la
fois sur une connexion donnée. Pour pouvoir réagir à un `interrupt` MÊME
pendant que le serveur traite la demande (agent LangGraph) ou envoie l'audio
TTS, une unique tâche `_pump_incoming_messages` lit en continu le WebSocket et
pousse chaque frame dans une `asyncio.Queue`. Le reste du code consomme
cette queue, ce qui permet de "courir" (`asyncio.wait(..., FIRST_COMPLETED)`)
entre "message de contrôle reçu" et "prochain morceau de travail terminé" à
n'importe quelle étape du tour — voir `_run_cancelable` et la boucle TTS.

§ TIMEOUT : si l'utilisateur ouvre une fenêtre de capture de commande (après
wake word ou appui manuel) mais ne dit rien pendant `COMMAND_TIMEOUT_SECONDS`,
le serveur abandonne cette capture et renvoie `command_timeout` plutôt que de
laisser la connexion bloquée indéfiniment en attente d'un `end_of_speech`.
"""

import asyncio
import json
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.application.use_cases.manage_conversation.process_message import ProcessConversationMessageUseCase
from src.core.dependencies import (
    get_calendar_provider,
    get_current_user_id_from_token,
    get_google_oauth_token_repository,
    get_llm_provider,
    get_stt_provider,
    get_task_repository,
    get_tts_provider,
)
from src.infrastructure.persistence.database import AsyncSessionLocal
from src.infrastructure.persistence.repositories.calendar_repository_impl import SQLAlchemyCalendarEventRepository
from src.infrastructure.persistence.repositories.google_oauth_token_repository_impl import (
    SQLAlchemyGoogleOAuthTokenRepository,
)
from src.infrastructure.persistence.repositories.memory_repository_impl import SQLAlchemyMemoryRepository
from src.infrastructure.persistence.repositories.task_repository_impl import SQLAlchemyTaskRepository

router = APIRouter()

# Fenêtre maximale d'attente d'un `end_of_speech` après le début d'une capture
# de commande (post wake word ou appui manuel), avant abandon automatique.
COMMAND_TIMEOUT_SECONDS = 15


class _Interrupted(Exception):
    """Levée en interne quand un `interrupt` (ou une déconnexion) survient pendant
    un traitement annulable (raisonnement agent ou streaming TTS)."""

    def __init__(self, disconnected: bool = False) -> None:
        self.disconnected = disconnected


async def _pump_incoming_messages(websocket: WebSocket, queue: "asyncio.Queue[dict]") -> None:
    """
    Unique lecteur du WebSocket (Starlette ne supporte qu'un seul `receive()`
    concurrent par connexion) : pousse chaque frame reçue dans `queue`. Voir
    § BARGE-IN en tête de fichier — c'est ce qui permet au reste du code de
    réagir à un `interrupt` à tout moment, pas seulement pendant l'écoute.
    """
    try:
        while True:
            message = await websocket.receive()
            await queue.put(message)
            if message.get("type") == "websocket.disconnect":
                return
    except WebSocketDisconnect:
        await queue.put({"type": "websocket.disconnect"})


def _parse_control_event(message: dict) -> Optional[str]:
    if "text" in message and message["text"] is not None:
        try:
            return json.loads(message["text"]).get("event")
        except json.JSONDecodeError:
            return None
    return None


def _parse_whatsapp_context(message: dict) -> Optional[dict]:
    """
    Extrait le contexte WhatsApp transitoire optionnel attaché par le client à
    `end_of_speech` (§ CONTEXTE, séparation des contextes) :

        {"event": "end_of_speech", "whatsapp_context": {"sender": "Paul", "text": "..."}}

    Le client (voir `WhatsAppNotifier` côté Flutter) ne l'attache QUE lorsqu'un
    message WhatsApp est réellement en attente de réponse au moment où
    l'utilisateur parle — absent dans le cas normal (aucun changement de
    comportement pour une commande vocale classique).
    """
    if "text" not in message or message["text"] is None:
        return None
    try:
        payload = json.loads(message["text"])
    except json.JSONDecodeError:
        return None
    context = payload.get("whatsapp_context")
    if not isinstance(context, dict):
        return None
    if not isinstance(context.get("text"), str) or not context["text"].strip():
        return None
    return {"sender": context.get("sender") or "un contact", "text": context["text"]}


async def _run_cancelable(coro, queue: "asyncio.Queue[dict]"):
    """
    Exécute `coro` jusqu'à son terme, SAUF si un `interrupt` (ou une
    déconnexion) est reçu sur `queue` avant : dans ce cas, `coro` est annulée
    et `_Interrupted` est levée. Permet un vrai barge-in pendant le
    raisonnement de l'agent (§ INTERRUPTION : "utilisateur parle pendant la
    réponse" couvre aussi la phase de traitement, pas seulement la lecture
    audio).
    """
    task = asyncio.ensure_future(coro)
    control_task = asyncio.ensure_future(queue.get())
    try:
        while True:
            done, _ = await asyncio.wait({task, control_task}, return_when=asyncio.FIRST_COMPLETED)
            if task in done:
                control_task.cancel()
                return task.result()

            message = control_task.result()
            if message.get("type") == "websocket.disconnect":
                task.cancel()
                raise _Interrupted(disconnected=True)
            if _parse_control_event(message) == "interrupt":
                task.cancel()
                raise _Interrupted()
            # Message de contrôle non pertinent à ce stade (ex. un deuxième
            # `end_of_speech` égaré) : on l'ignore et on continue d'attendre,
            # sans annuler le traitement en cours.
            control_task = asyncio.ensure_future(queue.get())
    finally:
        if not task.done():
            task.cancel()


@router.websocket("/ws/v1/voice")
async def voice_conversation_ws(websocket: WebSocket, token: str, voice_id: str = "default") -> None:
    """
    Canal vocal bidirectionnel. Authentification via `?token=<access_token>` en query param
    (voir `get_current_user_id_from_token` pour la justification de ce choix côté WebSocket).
    """
    try:
        user_id: UUID = get_current_user_id_from_token(token)
    except ValueError:
        await websocket.close(code=4401, reason="Token invalide ou expiré.")
        return

    await websocket.accept()

    stt_provider = get_stt_provider()
    tts_provider = get_tts_provider()
    llm_provider = get_llm_provider()

    conversation_history: list[dict] = []
    incoming: "asyncio.Queue[dict]" = asyncio.Queue()
    reader = asyncio.create_task(_pump_incoming_messages(websocket, incoming))

    try:
        while True:
            audio_buffer = bytearray()

            # --- Phase 1 : réception du flux audio jusqu'à end_of_speech (ou timeout) ---
            timed_out = False
            whatsapp_context: Optional[dict] = None
            while True:
                try:
                    message = await asyncio.wait_for(incoming.get(), timeout=COMMAND_TIMEOUT_SECONDS)
                except asyncio.TimeoutError:
                    timed_out = True
                    break

                if message.get("type") == "websocket.disconnect":
                    return

                if "bytes" in message and message["bytes"] is not None:
                    audio_buffer.extend(message["bytes"])
                    continue

                event = _parse_control_event(message)
                if event == "end_of_speech":
                    whatsapp_context = _parse_whatsapp_context(message)
                    break
                if event == "interrupt":
                    # Barge-in pendant l'écoute elle-même (ex. l'utilisateur
                    # recommence sa phrase) : on vide le buffer et on continue
                    # d'écouter la même fenêtre de capture.
                    audio_buffer.clear()
                    continue

            if timed_out:
                await websocket.send_text(json.dumps({"event": "command_timeout"}))
                continue

            if not audio_buffer:
                continue

            # --- Phase 2 : transcription (STT) ---
            transcript = await stt_provider.transcribe(bytes(audio_buffer))
            if not transcript:
                await websocket.send_text(json.dumps({"event": "transcript", "text": ""}))
                continue

            await websocket.send_text(json.dumps({"event": "transcript", "text": transcript}))
            await websocket.send_text(json.dumps({"event": "agent_thinking"}))

            # --- Phase 3 : raisonnement (orchestrateur LangGraph), annulable (barge-in) ---
            async def _process() -> Any:
                async with AsyncSessionLocal() as session:
                    task_repository = SQLAlchemyTaskRepository(session)
                    calendar_repository = SQLAlchemyCalendarEventRepository(session)
                    token_repository = SQLAlchemyGoogleOAuthTokenRepository(session)
                    memory_repository = SQLAlchemyMemoryRepository(session)
                    use_case = ProcessConversationMessageUseCase(
                        llm_provider,
                        task_repository,
                        calendar_repository,
                        get_calendar_provider(),
                        token_repository,
                        memory_repository,
                    )
                    return await use_case.execute(
                        user_id=user_id,
                        message=transcript,
                        history=conversation_history,
                        whatsapp_context=whatsapp_context,
                    )

            try:
                result = await _run_cancelable(_process(), incoming)
            except _Interrupted as interruption:
                if interruption.disconnected:
                    return
                await websocket.send_text(json.dumps({"event": "interrupted"}))
                continue

            conversation_history.append({"role": "user", "content": transcript})
            conversation_history.append({"role": "assistant", "content": result.response})

            if result.requires_confirmation:
                await websocket.send_text(
                    json.dumps({"event": "requires_confirmation", "tool_call": result.pending_tool_call})
                )

            for client_action in result.client_actions:
                await websocket.send_text(
                    json.dumps(
                        {
                            "event": "client_action",
                            "action": client_action.get("action"),
                            "payload": client_action.get("payload", {}),
                        }
                    )
                )

            # Résumé des outils déjà exécutés par l'agent (§ EXECUTING_ACTION côté
            # client). Limitation assumée : ceci est envoyé APRÈS coup (le graphe
            # LangGraph a déjà tout exécuté avant de retourner `result`), donc pas
            # un flux temps réel outil-par-outil — voir le rapport de livraison.
            if result.tool_trace:
                await websocket.send_text(
                    json.dumps(
                        {
                            "event": "tool_calls_summary",
                            "tools": [
                                {"tool": t["tool"], "success": t["result"].get("success", False)}
                                for t in result.tool_trace
                            ],
                        }
                    )
                )

            # --- Phase 4 : synthèse vocale (TTS), streamée chunk par chunk, annulable (barge-in) ---
            tts_stream = tts_provider.synthesize_stream(result.response, voice_id=voice_id).__aiter__()
            control_task = asyncio.ensure_future(incoming.get())
            interrupted = False
            try:
                while True:
                    chunk_task = asyncio.ensure_future(tts_stream.__anext__())
                    done, _ = await asyncio.wait({chunk_task, control_task}, return_when=asyncio.FIRST_COMPLETED)

                    if control_task in done:
                        message = control_task.result()
                        if message.get("type") == "websocket.disconnect":
                            chunk_task.cancel()
                            return
                        if _parse_control_event(message) == "interrupt":
                            chunk_task.cancel()
                            interrupted = True
                            await websocket.send_text(json.dumps({"event": "interrupted"}))
                            break
                        control_task = asyncio.ensure_future(incoming.get())
                        continue

                    try:
                        chunk = chunk_task.result()
                    except StopAsyncIteration:
                        break

                    if chunk["type"] == "audio":
                        await websocket.send_bytes(chunk["data"])
                    elif chunk["type"] == "word":
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "event": "response_word",
                                    "text": chunk["text"],
                                    "offset_ms": chunk["offset_ms"],
                                    "duration_ms": chunk["duration_ms"],
                                }
                            )
                        )
            finally:
                if not control_task.done():
                    control_task.cancel()

            if not interrupted:
                await websocket.send_text(json.dumps({"event": "response_text_final", "text": result.response}))

            await websocket.send_text(json.dumps({"event": "end_of_turn"}))

    except WebSocketDisconnect:
        return
    finally:
        reader.cancel()
