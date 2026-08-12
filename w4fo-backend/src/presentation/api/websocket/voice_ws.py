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
    {"event": "interrupt"}       → barge-in : annule la réponse en cours
- Le serveur envoie des frames TEXTE JSON pour les événements de contrôle :
    {"event": "transcript", "text": "..."}
    {"event": "agent_thinking"}
    {"event": "response_text", "text": "..."}
    {"event": "requires_confirmation", "tool_call": {...}}
    {"event": "end_of_turn"}
- Le serveur envoie des frames BINAIRES = chunks audio de la réponse (MP3).

Limitation V1 assumée : le graphe LangGraph est invoqué une fois le texte final
obtenu (pas de function calling en flux continu) ; le TTS démarre dès que la
réponse texte complète du tour est disponible. Le découpage phrase par phrase
pour réduire la latence (§10.2) sera affiné en V2.
"""

import json
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

    try:
        while True:
            audio_buffer = bytearray()

            # --- Phase 1 : réception du flux audio jusqu'à end_of_speech ---
            while True:
                message = await websocket.receive()

                if message.get("type") == "websocket.disconnect":
                    return

                if "bytes" in message and message["bytes"] is not None:
                    audio_buffer.extend(message["bytes"])
                    continue

                if "text" in message and message["text"] is not None:
                    control = json.loads(message["text"])
                    if control.get("event") == "end_of_speech":
                        break
                    if control.get("event") == "interrupt":
                        # Barge-in (§10.2) : on vide le buffer et on repart en écoute
                        audio_buffer.clear()
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

            # --- Phase 3 : raisonnement (orchestrateur LangGraph) ---
            # Une session DB dédiée est ouverte par tour de conversation, cohérent avec
            # le pattern "une session par requête" utilisé côté REST (get_db_session).
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
                result = await use_case.execute(user_id=user_id, message=transcript, history=conversation_history)

            conversation_history.append({"role": "user", "content": transcript})
            conversation_history.append({"role": "assistant", "content": result.response})

            if result.requires_confirmation:
                await websocket.send_text(
                    json.dumps({"event": "requires_confirmation", "tool_call": result.pending_tool_call})
                )

            await websocket.send_text(json.dumps({"event": "response_text", "text": result.response}))

            # --- Phase 4 : synthèse vocale (TTS), streamée chunk par chunk ---
            async for audio_chunk in tts_provider.synthesize_stream(result.response, voice_id=voice_id):
                await websocket.send_bytes(audio_chunk)

            await websocket.send_text(json.dumps({"event": "end_of_turn"}))

    except WebSocketDisconnect:
        return
