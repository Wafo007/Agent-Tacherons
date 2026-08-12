"""
Outils (tools) du module Tâches, exposés au LLM via function calling.

Chaque outil se compose de :
- une définition JSON Schema (format attendu par Mistral function calling) ;
- une fonction d'exécution qui appelle le use case applicatif correspondant.

Conformément au document d'architecture (§6.4), les tools sont classés par niveau
de sensibilité : `task_delete` est une action sensible et nécessite confirmation.
"""

from typing import Any
from uuid import UUID

from src.application.dto.task_dto import CreateTaskDTO, UpdateTaskDTO
from src.application.use_cases.manage_tasks.create_task import CreateTaskUseCase
from src.application.use_cases.manage_tasks.delete_task import DeleteTaskUseCase
from src.application.use_cases.manage_tasks.list_tasks import ListTasksUseCase
from src.application.use_cases.manage_tasks.update_task import UpdateTaskUseCase
from src.domain.repositories.task_repository import TaskRepository
from src.domain.value_objects.priority import Priority, TaskStatus

# --- Classification de sensibilité des outils (§6.4 du document d'architecture) ---
SENSITIVE_TOOLS: set[str] = {"task_delete"}

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
            "description": "Liste les tâches de l'utilisateur, avec filtres optionnels par statut ou catégorie.",
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
            "description": "Met à jour une tâche existante (statut, priorité, titre...).",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Identifiant UUID de la tâche."},
                    "status": {"type": "string", "enum": [s.value for s in TaskStatus]},
                    "priority": {"type": "string", "enum": [p.value for p in Priority]},
                    "title": {"type": "string"},
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
    """
    if tool_name == "task_create":
        use_case = CreateTaskUseCase(task_repository)
        task = await use_case.execute(
            CreateTaskDTO(
                user_id=user_id,
                title=arguments["title"],
                description=arguments.get("description", ""),
                priority=Priority(arguments["priority"]) if arguments.get("priority") else Priority.MEDIUM,
                category=arguments.get("category", "general"),
            )
        )
        return {"id": str(task.id), "title": task.title, "status": task.status.value}

    if tool_name == "task_list":
        use_case = ListTasksUseCase(task_repository)
        status = TaskStatus(arguments["status"]) if arguments.get("status") else None
        tasks = await use_case.execute(user_id, status=status, category=arguments.get("category"))
        return {"tasks": [{"id": str(t.id), "title": t.title, "status": t.status.value} for t in tasks]}

    if tool_name == "task_update":
        use_case = UpdateTaskUseCase(task_repository)
        task = await use_case.execute(
            UpdateTaskDTO(
                task_id=UUID(arguments["task_id"]),
                title=arguments.get("title"),
                status=TaskStatus(arguments["status"]) if arguments.get("status") else None,
                priority=Priority(arguments["priority"]) if arguments.get("priority") else None,
            )
        )
        return {"id": str(task.id), "status": task.status.value}

    if tool_name == "task_delete":
        use_case = DeleteTaskUseCase(task_repository)
        await use_case.execute(UUID(arguments["task_id"]))
        return {"deleted": True, "task_id": arguments["task_id"]}

    raise ValueError(f"Outil inconnu : {tool_name}")
