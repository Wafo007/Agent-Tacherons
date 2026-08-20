"""Endpoints CRUD pour la gestion des tâches (module `task`)."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.application.dto.task_dto import CreateTaskDTO, UpdateTaskDTO
from src.application.use_cases.manage_tasks.create_task import CreateTaskUseCase
from src.application.use_cases.manage_tasks.delete_task import DeleteTaskUseCase
from src.application.use_cases.manage_tasks.list_tasks import ListTasksUseCase
from src.application.use_cases.manage_tasks.update_task import UpdateTaskUseCase
from src.core.dependencies import CurrentUserId, TaskRepo
from src.core.exceptions import EntityNotFoundError, UnauthorizedError
from src.domain.value_objects.priority import TaskStatus
from src.presentation.schemas.task_schema import CreateTaskRequest, TaskResponse, UpdateTaskRequest

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(request: CreateTaskRequest, user_id: CurrentUserId, task_repository: TaskRepo) -> TaskResponse:
    use_case = CreateTaskUseCase(task_repository)
    task = await use_case.execute(
        CreateTaskDTO(
            user_id=user_id,
            title=request.title,
            description=request.description,
            due_date=request.due_date,
            priority=request.priority,
            category=request.category,
        )
    )
    return TaskResponse.model_validate(task)


@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    user_id: CurrentUserId,
    task_repository: TaskRepo,
    status_filter: Optional[TaskStatus] = None,
    category: Optional[str] = None,
) -> List[TaskResponse]:
    use_case = ListTasksUseCase(task_repository)
    tasks = await use_case.execute(user_id, status=status_filter, category=category)
    return [TaskResponse.model_validate(t) for t in tasks]


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID, request: UpdateTaskRequest, user_id: CurrentUserId, task_repository: TaskRepo
) -> TaskResponse:
    use_case = UpdateTaskUseCase(task_repository)
    try:
        task = await use_case.execute(
            UpdateTaskDTO(
                task_id=task_id,
                title=request.title,
                description=request.description,
                due_date=request.due_date,
                priority=request.priority,
                status=request.status,
                category=request.category,
            ),
            user_id=user_id,
        )
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return TaskResponse.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: UUID, user_id: CurrentUserId, task_repository: TaskRepo) -> None:
    use_case = DeleteTaskUseCase(task_repository)
    try:
        await use_case.execute(task_id, user_id=user_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
