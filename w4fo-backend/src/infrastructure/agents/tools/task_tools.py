"""
Outils (tools) du module Tâches, exposés au LLM via function calling.

Chaque outil se compose de :
- une définition JSON Schema (format attendu par Mistral function calling) ;
- une fonction d'exécution qui appelle le use case applicatif correspondant.

Conformément au document d'architecture (§6.4), les tools sont classés par niveau
de sensibilité : `task_delete` est une action sensible et nécessite confirmation.

§ DATE ET HEURE (fiabilisation de la création/mise à jour de tâches) :
`task_create` et `task_update` acceptent un champ `due_date` en texte libre.
Le LLM est invité (voir description du champ + prompt système de l'agent,
`nodes/agent_node.py`, qui lui fournit la date/heure actuelles réelles) à
transmettre directement une date ISO 8601 déjà calculée. En secours,
`parse_datetime_expression` (`datetime_parser.py`) sait aussi résoudre une
expression française brute ("demain à 18h", "vendredi prochain"...) si le
LLM la transmet telle quelle. Toute date non résolvable renvoie une erreur
structurée — jamais un crash (voir `ToolRegistry.execute`).

§ CRUD fiable : tous les outils retournent maintenant l'intégralité des
champs utiles de la tâche (titre, description, due_date, priorité, statut,
catégorie) — indispensable pour qu'un enchaînement multi-outils du type
"liste mes tâches, trouve celle de demain, déplace-la à vendredi" puisse
identifier la bonne tâche à partir du résultat de `task_list`.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from src.application.dto.task_dto import CreateTaskDTO, UpdateTaskDTO
from src.application.use_cases.manage_tasks.create_task import CreateTaskUseCase
from src.application.use_cases.manage_tasks.delete_task import DeleteTaskUseCase
from src.application.use_cases.manage_tasks.list_tasks import ListTasksUseCase
from src.application.use_cases.manage_tasks.update_task import UpdateTaskUseCase
from src.core.config import get_settings
from src.domain.entities.task import Task
from src.domain.repositories.task_repository import TaskRepository
from src.domain.value_objects.priority import Priority, TaskStatus
from src.infrastructure.agents.tools.datetime_parser import parse_datetime_expression

# --- Classification de sensibilité des outils (§6.4 du document d'architecture) ---
SENSITIVE_TOOLS: set[str] = {"task_delete"}

_DUE_DATE_DESCRIPTION = (
    "Date/heure d'échéance (optionnelle). Fournis de préférence une date ISO 8601 "
    "déjà calculée à partir de la date/heure actuelles données dans le contexte "
    "(ex: '2026-08-23T18:00:00'). Une expression simple comme 'demain à 18h' ou "
    "'vendredi prochain' est aussi acceptée en secours."
)

# --- Définitions JSON Schema exposées au LLM (format Mistral function calling) ---

TASK_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "task_create",
            "description": "Crée une nouvelle tâche pour l'utilisateur.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Titre court de la tâche."},
                    "description": {"type": "string", "description": "Description détaillée (optionnelle)."},
                    "due_date": {"type": "string", "description": _DUE_DATE_DESCRIPTION},
                    "priority": {
                        "type": "string",
                        "enum": [p.value for p in Priority],
                        "description": "Niveau de priorité.",
                    },
                    "category": {"type": "string", "description": "Catégorie de la tâche."},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "task_list",
            "description": (
                "Liste les tâches de l'utilisateur, avec filtres optionnels par statut ou catégorie. "
                "Retourne pour chaque tâche son id, titre, description, échéance, priorité, statut et "
                "catégorie — utilise ces informations pour identifier une tâche précise avant de la "
                "modifier ou de la supprimer (ex: 'la tâche de demain', 'ma tâche pour appeler Paul')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": [s.value for s in TaskStatus]},
                    "category": {"type": "string"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "task_update",
            "description": (
                "Met à jour une tâche existante (titre, description, échéance, statut, priorité, "
                "catégorie...). Utilise `task_list` au préalable si tu ne connais pas déjà le "
                "`task_id` exact."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Identifiant UUID de la tâche."},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "due_date": {"type": "string", "description": _DUE_DATE_DESCRIPTION},
                    "status": {"type": "string", "enum": [s.value for s in TaskStatus]},
                    "priority": {"type": "string", "enum": [p.value for p in Priority]},
                    "category": {"type": "string"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "task_delete",
            "description": "Supprime définitivement une tâche. Action sensible nécessitant confirmation.",
            "parameters": {
                "type": "object",
                "properties": {"task_id": {"type": "string", "description": "Identifiant UUID de la tâche."}},
                "required": ["task_id"],
            },
        },
    },
]


def _current_reference_time() -> datetime:
    """Heure actuelle réelle, dans le fuseau applicatif (voir `settings.app_timezone`)."""
    return datetime.now(ZoneInfo(get_settings().app_timezone))


def _resolve_due_date(raw_value: Optional[str]) -> Optional[datetime]:
    """Résout un champ `due_date` optionnel. Ne fait rien si absent/vide (tâche sans échéance)."""
    if not raw_value:
        return None
    return parse_datetime_expression(raw_value, now=_current_reference_time())


def _serialize_task(task: Task) -> dict[str, Any]:
    """Représentation complète et structurée d'une tâche, pour observation LLM."""
    return {
        "id": str(task.id),
        "title": task.title,
        "description": task.description,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "priority": task.priority.value,
        "status": task.status.value,
        "category": task.category,
    }


async def execute_task_tool(
    tool_name: str,
    arguments: dict[str, Any],
    user_id: UUID,
    task_repository: TaskRepository,
) -> dict[str, Any]:
    """
    Exécute un outil Task par son nom, en déléguant au use case applicatif approprié.

    Retourne un dict sérialisable, destiné à être réinjecté dans la conversation
    comme résultat d'outil (observation) pour que le LLM poursuive son raisonnement.
    Une date invalide, un statut/priorité inconnu, un identifiant de tâche appartenant
    à un autre utilisateur, etc. lèvent une exception métier explicite (jamais un
    crash silencieux) — `ToolRegistry.execute` la convertit en résultat structuré
    `{"success": False, "error": ...}`.
    """
    if tool_name == "task_create":
        use_case = CreateTaskUseCase(task_repository)
        task = await use_case.execute(
            CreateTaskDTO(
                user_id=user_id,
                title=arguments["title"],
                description=arguments.get("description", ""),
                due_date=_resolve_due_date(arguments.get("due_date")),
                priority=Priority(arguments["priority"]) if arguments.get("priority") else Priority.MEDIUM,
                category=arguments.get("category", "general"),
            )
        )
        return _serialize_task(task)

    if tool_name == "task_list":
        use_case = ListTasksUseCase(task_repository)
        status_filter = TaskStatus(arguments["status"]) if arguments.get("status") else None
        tasks = await use_case.execute(user_id, status=status_filter, category=arguments.get("category"))
        return {"tasks": [_serialize_task(t) for t in tasks]}

    if tool_name == "task_update":
        use_case = UpdateTaskUseCase(task_repository)
        task = await use_case.execute(
            UpdateTaskDTO(
                task_id=UUID(arguments["task_id"]),
                title=arguments.get("title"),
                description=arguments.get("description"),
                due_date=_resolve_due_date(arguments.get("due_date")),
                status=TaskStatus(arguments["status"]) if arguments.get("status") else None,
                priority=Priority(arguments["priority"]) if arguments.get("priority") else None,
                category=arguments.get("category"),
            ),
            user_id=user_id,
        )
        return _serialize_task(task)

    if tool_name == "task_delete":
        use_case = DeleteTaskUseCase(task_repository)
        task_id = arguments["task_id"]
        await use_case.execute(UUID(task_id), user_id=user_id)
        return {"deleted": True, "task_id": task_id}

    raise ValueError(f"Outil inconnu : {tool_name}")
