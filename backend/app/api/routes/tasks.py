from datetime import date
from math import ceil
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import case, delete, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_current_manager, get_current_user, get_db
from app.models.project import Project, project_members
from app.models.task import Task, TaskPriority, TaskStatus, task_assignees, task_blockers
from app.models.user import User, UserRole
from app.schemas.tasks import AssignedTaskResponse, TaskResponse, TaskSearchResponse, TaskStatusChangeRequest, TaskWriteRequest

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _task_query():
    return select(Task).options(selectinload(Task.blockers), selectinload(Task.assignees))


def _visible_task_filters(user: User) -> list:
    filters = [Task.deleted.is_(False), Project.archived.is_(False)]
    if user.role == UserRole.MEMBER:
        filters.append(project_members.c.user_id == user.id)
    return filters


def _task_search_statement(user: User):
    statement = _task_query().join(Project)
    if user.role == UserRole.MEMBER:
        statement = statement.join(project_members)
    return statement


def _clean_title(title: str) -> str:
    clean_title = title.strip()
    if not clean_title:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Task title cannot be blank.")
    return clean_title


def _get_visible_project(session: Session, project_id: int, user: User) -> Project:
    statement = select(Project).where(Project.id == project_id)
    if user.role == UserRole.MEMBER:
        statement = statement.join(project_members).where(project_members.c.user_id == user.id)
    project = session.scalar(statement)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


def _get_visible_task(session: Session, task_id: int, user: User) -> Task:
    task = session.scalar(_task_query().where(Task.id == task_id, Task.deleted.is_(False)))
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    _get_visible_project(session, task.project_id, user)
    return task


def _set_blockers(session: Session, task: Task, blocker_ids: list[int]) -> None:
    requested_ids = set(blocker_ids)
    if task.id and task.id in requested_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="A task cannot block itself.")
    if not requested_ids:
        task.blockers = []
        return
    blockers = list(
        session.scalars(
            _task_query().where(
                Task.id.in_(requested_ids),
                Task.project_id == task.project_id,
                Task.deleted.is_(False),
            )
        )
    )
    found_ids = {blocker.id for blocker in blockers}
    if found_ids != requested_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Every blocker must be an active task in the same project.",
        )
    task.blockers = blockers


def _set_assignees(session: Session, task: Task, assignee_ids: list[int]) -> None:
    requested_ids = set(assignee_ids)
    if not requested_ids:
        task.assignees = []
        return
    assignees = list(
        session.scalars(
            select(User)
            .join(project_members)
            .where(User.id.in_(requested_ids), project_members.c.project_id == task.project_id)
        )
    )
    found_ids = {assignee.id for assignee in assignees}
    if found_ids != requested_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Every assignee must be a member of this task's project.",
        )
    task.assignees = assignees


def _move_task(task: Task, target_status: TaskStatus) -> None:
    if target_status not in task.available_statuses:
        if (
            task.status == TaskStatus.IN_REVIEW
            and target_status == TaskStatus.DONE
            and any(blocker.status != TaskStatus.DONE for blocker in task.blockers)
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Task cannot move to Done while unfinished blocking tasks remain.",
            )
        legal_moves = ", ".join(move.value.replace("_", " ").title() for move in task.available_statuses) or "none"
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Task cannot move from {task.status.value.replace('_', ' ').title()} "
                f"to {target_status.value.replace('_', ' ').title()}. Legal moves: {legal_moves}."
            ),
        )
    task.blocked_from = task.status if target_status == TaskStatus.BLOCKED else None
    task.status = target_status


@router.get("/projects/{project_id}", response_model=list[TaskResponse])
def list_project_tasks(
    project_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[Task]:
    _get_visible_project(session, project_id, user)
    return list(session.scalars(_task_query().where(Task.project_id == project_id, Task.deleted.is_(False)).order_by(Task.updated_at.desc())))


@router.get("/assigned", response_model=list[AssignedTaskResponse])
def list_assigned_tasks(user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> list[Task]:
    return list(
        session.scalars(
            _task_query()
            .options(selectinload(Task.project))
            .join(task_assignees)
            .where(task_assignees.c.user_id == user.id, Task.deleted.is_(False))
            .order_by(Task.updated_at.desc())
        )
    )


@router.get("", response_model=TaskSearchResponse)
def search_tasks(
    q: str = Query(default="", max_length=300),
    project_id: int | None = None,
    task_status: TaskStatus | None = Query(default=None, alias="status"),
    assignee_id: int | None = None,
    priority: TaskPriority | None = None,
    overdue: bool = False,
    sort_by: Literal["due_date", "priority", "updated_at"] = "updated_at",
    sort_direction: Literal["asc", "desc"] = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> TaskSearchResponse:
    filters = _visible_task_filters(user)
    clean_query = q.strip()
    if clean_query:
        filters.append(or_(Task.title.ilike(f"%{clean_query}%"), Task.description.ilike(f"%{clean_query}%")))
    if project_id is not None:
        filters.append(Task.project_id == project_id)
    if task_status is not None:
        filters.append(Task.status == task_status)
    if assignee_id is not None:
        filters.append(Task.assignees.any(User.id == assignee_id))
    if priority is not None:
        filters.append(Task.priority == priority)
    if overdue:
        filters.extend([Task.due_date.is_not(None), Task.due_date < date.today(), Task.status != TaskStatus.DONE])

    count_statement = select(func.count(Task.id)).select_from(Task).join(Project)
    if user.role == UserRole.MEMBER:
        count_statement = count_statement.join(project_members)
    total = session.scalar(count_statement.where(*filters)) or 0
    if sort_by == "due_date":
        null_due_dates_last = case((Task.due_date.is_(None), 1), else_=0).asc()
        sort_column = Task.due_date
        order_by = [null_due_dates_last, sort_column.asc() if sort_direction == "asc" else sort_column.desc()]
    elif sort_by == "priority":
        priority_rank = case(
            (Task.priority == TaskPriority.LOW, 1),
            (Task.priority == TaskPriority.MEDIUM, 2),
            (Task.priority == TaskPriority.HIGH, 3),
            (Task.priority == TaskPriority.CRITICAL, 4),
            else_=0,
        )
        order_by = [priority_rank.asc() if sort_direction == "asc" else priority_rank.desc()]
    else:
        order_by = [Task.updated_at.asc() if sort_direction == "asc" else Task.updated_at.desc()]

    tasks = list(
        session.scalars(
            _task_search_statement(user)
            .where(*filters)
            .options(selectinload(Task.project))
            .order_by(*order_by, Task.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return TaskSearchResponse(
        items=tasks,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size),
    )


@router.post("/projects/{project_id}", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    project_id: int,
    payload: TaskWriteRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Task:
    _get_visible_project(session, project_id, user)
    task = Task(
        project_id=project_id,
        title=_clean_title(payload.title),
        description=payload.description.strip(),
        priority=payload.priority,
        due_date=payload.due_date,
    )
    session.add(task)
    session.flush()
    _set_blockers(session, task, payload.blocker_ids)
    _set_assignees(session, task, payload.assignee_ids)
    session.commit()
    return session.scalar(_task_query().where(Task.id == task.id))


@router.post("/{task_id}/status", response_model=TaskResponse)
def change_task_status(
    task_id: int,
    payload: TaskStatusChangeRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Task:
    task = _get_visible_task(session, task_id, user)
    _move_task(task, payload.status)
    session.commit()
    return session.scalar(_task_query().where(Task.id == task.id))


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> Task:
    return _get_visible_task(session, task_id, user)


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    payload: TaskWriteRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Task:
    task = _get_visible_task(session, task_id, user)
    task.title = _clean_title(payload.title)
    task.description = payload.description.strip()
    task.priority = payload.priority
    task.due_date = payload.due_date
    _set_blockers(session, task, payload.blocker_ids)
    _set_assignees(session, task, payload.assignee_ids)
    if task.status == TaskStatus.DONE and any(blocker.status != TaskStatus.DONE for blocker in task.blockers):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A done task cannot have unfinished blocking tasks.",
        )
    session.commit()
    return session.scalar(_task_query().where(Task.id == task.id))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    _: User = Depends(get_current_manager),
    session: Session = Depends(get_db),
) -> Response:
    task = session.get(Task, task_id)
    if not task or task.deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    session.execute(
        delete(task_blockers).where(
            or_(task_blockers.c.task_id == task.id, task_blockers.c.blocking_task_id == task.id)
        )
    )
    task.deleted = True
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
