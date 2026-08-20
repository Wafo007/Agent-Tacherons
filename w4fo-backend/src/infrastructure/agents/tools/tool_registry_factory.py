"""
Point d'assemblage du registre d'outils pour un tour de conversation.

Construit un `ToolRegistry` à partir des définitions déjà existantes de
chaque domaine (`task_tools.py`, `calendar_tools.py`), SANS dupliquer les
schémas JSON ni la logique d'exécution qui y sont déjà correctement définis.
On se contente de les enregistrer dans le registre central, avec les
dépendances (repositories, providers) pré-liées.

Pour ajouter un nouveau domaine d'outils (MemoryTools, WhatsAppTools,
NotificationTools, AppTools, VoiceTools...) : créer son propre
`xxx_tools.py` suivant le même schéma que `task_tools.py`
(TOOL_DEFINITIONS + SENSITIVE_TOOLS + execute_xxx_tool), puis ajouter une
boucle `for definition in XXX_TOOL_DEFINITIONS: registry.register(...)`
ci-dessous. Aucune autre partie de la boucle agentique n'a besoin d'être
modifiée.
"""

from functools import partial
from typing import Any
from uuid import UUID

from src.domain.repositories.calendar_repository import CalendarEventRepository
from src.domain.repositories.google_oauth_token_repository import GoogleOAuthTokenRepository
from src.domain.repositories.task_repository import TaskRepository
from src.domain.services.calendar_provider import CalendarProvider
from src.infrastructure.actions.action_registry import build_default_action_registry
from src.infrastructure.agents.tools.app_tools import (
    APP_TOOL_DEFINITIONS,
    SENSITIVE_APP_TOOLS,
    execute_app_tool,
)
from src.infrastructure.agents.tools.calendar_tools import (
    CALENDAR_TOOL_DEFINITIONS,
    SENSITIVE_CALENDAR_TOOLS,
    execute_calendar_tool,
)
from src.infrastructure.agents.tools.registry import ToolRegistry, ToolSpec
from src.infrastructure.agents.tools.task_tools import (
    SENSITIVE_TOOLS as SENSITIVE_TASK_TOOLS,
)
from src.infrastructure.agents.tools.task_tools import (
    TASK_TOOL_DEFINITIONS,
    execute_task_tool,
)


async def _run_task_tool(
    *, tool_name: str, task_repository: TaskRepository, arguments: dict[str, Any], user_id: UUID
) -> dict[str, Any]:
    return await execute_task_tool(
        tool_name=tool_name, arguments=arguments, user_id=user_id, task_repository=task_repository
    )


async def _run_calendar_tool(
    *,
    tool_name: str,
    calendar_repository: CalendarEventRepository,
    calendar_provider: CalendarProvider,
    token_repository: GoogleOAuthTokenRepository,
    arguments: dict[str, Any],
    user_id: UUID,
) -> dict[str, Any]:
    return await execute_calendar_tool(
        tool_name=tool_name,
        arguments=arguments,
        user_id=user_id,
        calendar_repository=calendar_repository,
        calendar_provider=calendar_provider,
        token_repository=token_repository,
    )


async def _run_app_tool(
    *, tool_name: str, action_registry, arguments: dict[str, Any], user_id: Any
) -> dict[str, Any]:
    # `user_id` n'est pas utilisé par les actions applicatives (navigation pure,
    # sans donnée utilisateur), mais l'interface commune `ToolExecutor` l'impose
    # (voir registry.py) pour rester strictement identique quel que soit le domaine.
    return await execute_app_tool(tool_name=tool_name, arguments=arguments, action_registry=action_registry)


def build_tool_registry(
    task_repository: TaskRepository,
    calendar_repository: CalendarEventRepository,
    calendar_provider: CalendarProvider,
    token_repository: GoogleOAuthTokenRepository,
) -> ToolRegistry:
    """Assemble le registre complet (Task + Calendar) pour le tour de conversation courant."""
    registry = ToolRegistry()

    for definition in TASK_TOOL_DEFINITIONS:
        name = definition["function"]["name"]
        registry.register(
            ToolSpec(
                name=name,
                description=definition["function"]["description"],
                parameters=definition["function"]["parameters"],
                executor=partial(_run_task_tool, tool_name=name, task_repository=task_repository),
                sensitive=name in SENSITIVE_TASK_TOOLS,
            )
        )

    for definition in CALENDAR_TOOL_DEFINITIONS:
        name = definition["function"]["name"]
        registry.register(
            ToolSpec(
                name=name,
                description=definition["function"]["description"],
                parameters=definition["function"]["parameters"],
                executor=partial(
                    _run_calendar_tool,
                    tool_name=name,
                    calendar_repository=calendar_repository,
                    calendar_provider=calendar_provider,
                    token_repository=token_repository,
                ),
                sensitive=name in SENSITIVE_CALENDAR_TOOLS,
            )
        )

    # --- Outils applicatifs (Action Gateway) : navigation Flutter ---
    # Un seul registre par tour de conversation suffit : ces actions n'ont pas
    # d'état, elles ne font que valider un code puis construire un payload.
    action_registry = build_default_action_registry()
    for definition in APP_TOOL_DEFINITIONS:
        name = definition["function"]["name"]
        registry.register(
            ToolSpec(
                name=name,
                description=definition["function"]["description"],
                parameters=definition["function"]["parameters"],
                executor=partial(_run_app_tool, tool_name=name, action_registry=action_registry),
                sensitive=name in SENSITIVE_APP_TOOLS,
            )
        )

    return registry
