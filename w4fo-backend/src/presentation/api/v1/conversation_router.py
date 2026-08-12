"""
Endpoint de conversation textuelle, orchestrée par le graphe LangGraph.

Ce endpoint REST est la première étape de validation du flux agentique de bout
en bout, avant l'ajout du WebSocket vocal (STT/TTS) prévu à l'étape suivante
de la roadmap. Il permet de tester le routage router → chat/task agent,
le tool calling, et le mécanisme de confirmation des actions sensibles.
"""

from fastapi import APIRouter

from src.application.use_cases.manage_conversation.process_message import ProcessConversationMessageUseCase
from src.core.dependencies import (
    CalendarProviderDep,
    CalendarRepo,
    CurrentUserId,
    GoogleTokenRepo,
    LLMProviderDep,
    MemoryRepo,
    TaskRepo,
)
from src.presentation.schemas.conversation_schema import MessageRequest, MessageResponse

router = APIRouter(prefix="/api/v1/conversation", tags=["conversation"])


@router.post("/message", response_model=MessageResponse)
async def send_message(
    request: MessageRequest,
    user_id: CurrentUserId,
    llm_provider: LLMProviderDep,
    task_repository: TaskRepo,
    calendar_repository: CalendarRepo,
    calendar_provider: CalendarProviderDep,
    token_repository: GoogleTokenRepo,
    memory_repository: MemoryRepo,
) -> MessageResponse:
    """
    Envoie un message utilisateur à l'orchestrateur d'agents et retourne la réponse.

    Si l'action détectée est sensible (ex: suppression de tâche ou d'événement),
    la réponse contient `requires_confirmation=True` : le client doit alors
    renvoyer le message avec une confirmation explicite avant exécution
    (mécanisme affiné lors de l'implémentation du flux de confirmation complet en V2).
    """
    use_case = ProcessConversationMessageUseCase(
        llm_provider, task_repository, calendar_repository, calendar_provider, token_repository, memory_repository
    )
    result = await use_case.execute(user_id=user_id, message=request.content, history=request.history)

    return MessageResponse(
        response=result.response,
        requires_confirmation=result.requires_confirmation,
        pending_tool_call=result.pending_tool_call,
    )
