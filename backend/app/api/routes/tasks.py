import csv
from datetime import date, datetime, timezone
from io import StringIO
from math import ceil
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import case, delete, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_current_manager, get_current_user, get_db
from app.models.project import Project, project_members
from app.models.task import Task, TaskPriority, TaskStatus, task_assignees, task_blockers
from app.models.task_activity import TaskActivity
from app.models.user import User, UserRole
from app.services.task_alerts import restore_task_alerts
from app.services.task_history import record_task_activity
from app.schemas.tasks import (
    AssignedTaskResponse,
    BulkTaskResult,
    BulkTaskUpdateResponse,
    TaskBulkUpdateRequest,
    TaskCommentRequest,
    TaskResponse,
    TaskSearchResponse,
    TaskStatusChangeRequest,
    TaskTimelineEvent,
    TaskWriteRequest,
)

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


def _task_search_filters(
    user: User,
    q: str,
    project_id: int | None,
    task_status: TaskStatus | None,
    assignee_id: int | None,
    priority: TaskPriority | None,
    overdue: bool,
) -> list:
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
    return filters


def _task_order_by(sort_by: str, sort_direction: str) -> list:
    if sort_by == "due_date":
        null_due_dates_last = case((Task.due_date.is_(None), 1), else_=0).asc()
        due_date_order = Task.due_date.asc() if sort_direction == "asc" else Task.due_date.desc()
        return [null_due_dates_last, due_date_order]
    if sort_by == "priority":
        priority_rank = case(
            (Task.priority == TaskPriority.LOW, 1),
            (Task.priority == TaskPriority.MEDIUM, 2),
            (Task.priority == TaskPriority.HIGH, 3),
            (Task.priority == TaskPriority.CRITICAL, 4),
            else_=0,
        )
        return [priority_rank.asc() if sort_direction == "asc" else priority_rank.desc()]
    return [Task.updated_at.asc() if sort_direction == "asc" else Task.updated_at.desc()]


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


def _blocker_names(tasks: list[Task]) -> str | None:
    return ", ".join(sorted(task.title for task in tasks)) or None


def _set_blockers(session: Session, task: Task, blocker_ids: list[int], actor: User) -> None:
    previous_value = _blocker_names(task.blockers)
    requested_ids = set(blocker_ids)
    if task.id and task.id in requested_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="A task cannot block itself.")
    if not requested_ids:
        task.blockers = []
        if previous_value:
            record_task_activity(session, task, actor, "FIELD_CHANGED", field_name="blockers", old_value=previous_value)
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
    next_value = _blocker_names(blockers)
    if previous_value != next_value:
        record_task_activity(
            session, task, actor, "FIELD_CHANGED", field_name="blockers", old_value=previous_value, new_value=next_value
        )


def _set_assignees(session: Session, task: Task, assignee_ids: list[int], actor: User) -> None:
    previous_assignees = {assignee.id: assignee for assignee in task.assignees}
    requested_ids = set(assignee_ids)
    if not requested_ids:
        task.assignees = []
        for assignee in previous_assignees.values():
            record_task_activity(session, task, actor, "UNASSIGNED", field_name="assignee", old_value=assignee.name)
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
    current_assignees = {assignee.id: assignee for assignee in assignees}
    for assignee_id in sorted(previous_assignees.keys() - current_assignees.keys()):
        record_task_activity(session, task, actor, "UNASSIGNED", field_name="assignee", old_value=previous_assignees[assignee_id].name)
    for assignee_id in sorted(current_assignees.keys() - previous_assignees.keys()):
        record_task_activity(session, task, actor, "ASSIGNED", field_name="assignee", new_value=current_assignees[assignee_id].name)


def _move_task(session: Session, task: Task, target_status: TaskStatus, actor: User) -> None:
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
    previous_status = task.status
    task.blocked_from = task.status if target_status == TaskStatus.BLOCKED else None
    task.status = target_status
    task.completed_at = datetime.now(timezone.utc) if target_status == TaskStatus.DONE else None
    record_task_activity(
        session,
        task,
        actor,
        "FIELD_CHANGED",
        field_name="status",
        old_value=previous_status.value,
        new_value=target_status.value,
    )


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
    filters = _task_search_filters(user, q, project_id, task_status, assignee_id, priority, overdue)

    count_statement = select(func.count(Task.id)).select_from(Task).join(Project)
    if user.role == UserRole.MEMBER:
        count_statement = count_statement.join(project_members)
    total = session.scalar(count_statement.where(*filters)) or 0
    order_by = _task_order_by(sort_by, sort_direction)

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


@router.get("/export")
def export_tasks(
    q: str = Query(default="", max_length=300),
    project_id: int | None = None,
    task_status: TaskStatus | None = Query(default=None, alias="status"),
    assignee_id: int | None = None,
    priority: TaskPriority | None = None,
    overdue: bool = False,
    sort_by: Literal["due_date", "priority", "updated_at"] = "updated_at",
    sort_direction: Literal["asc", "desc"] = "desc",
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Response:
    """Export every visible task that matches the same server-side finder filters."""
    filters = _task_search_filters(user, q, project_id, task_status, assignee_id, priority, overdue)
    tasks = list(
        session.scalars(
            _task_search_statement(user)
            .where(*filters)
            .options(selectinload(Task.project))
            .order_by(*_task_order_by(sort_by, sort_direction), Task.id.desc())
        )
    )

    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Project key", "Project", "Title", "Description", "Status", "Priority", "Due date", "Assignees", "Last updated"])
    for task in tasks:
        writer.writerow(
            [
                task.project.key,
                task.project.name,
                task.title,
                task.description,
                task.status.value,
                task.priority.value,
                task.due_date.isoformat() if task.due_date else "",
                ", ".join(assignee.name for assignee in task.assignees),
                task.updated_at.isoformat() if task.updated_at else "",
            ]
        )
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="northstar-tasks.csv"'},
    )


def _validate_bulk_request(payload: TaskBulkUpdateRequest) -> None:
    if payload.action == "status" and payload.status is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Choose a status for the bulk change.")


@router.post("/bulk", response_model=BulkTaskUpdateResponse)
def bulk_update_tasks(
    payload: TaskBulkUpdateRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> BulkTaskUpdateResponse:
    """Apply one change per task, retaining successful updates when siblings fail."""
    _validate_bulk_request(payload)
    results: list[BulkTaskResult] = []

    for task_id in dict.fromkeys(payload.task_ids):
        try:
            with session.begin_nested():
                task = _get_visible_task(session, task_id, user)
                if payload.action == "status":
                    _move_task(session, task, payload.status, user)
                    detail = f"Moved to {task.status.value.replace('_', ' ').title()}."
                elif payload.action == "assignees":
                    _set_assignees(session, task, payload.assignee_ids, user)
                    detail = "Assignees replaced."
                else:
                    previous_due_date = task.due_date.isoformat() if task.due_date else None
                    task.due_date = payload.due_date
                    next_due_date = task.due_date.isoformat() if task.due_date else None
                    if previous_due_date != next_due_date:
                        restore_task_alerts(session, task.id)
                        record_task_activity(
                            session,
                            task,
                            user,
                            "FIELD_CHANGED",
                            field_name="due date",
                            old_value=previous_due_date,
                            new_value=next_due_date,
                        )
                    detail = "Due date updated."
                session.flush()
                results.append(BulkTaskResult(task_id=task_id, succeeded=True, detail=detail, task=task))
        except HTTPException as error:
            results.append(BulkTaskResult(task_id=task_id, succeeded=False, detail=str(error.detail)))

    session.commit()
    return BulkTaskUpdateResponse(
        results=results,
        succeeded=sum(result.succeeded for result in results),
        rejected=sum(not result.succeeded for result in results),
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
    record_task_activity(session, task, user, "CREATED")
    _set_blockers(session, task, payload.blocker_ids, user)
    _set_assignees(session, task, payload.assignee_ids, user)
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
    _move_task(session, task, payload.status, user)
    session.commit()
    return session.scalar(_task_query().where(Task.id == task.id))


@router.get("/{task_id}/timeline", response_model=list[TaskTimelineEvent])
def get_task_timeline(task_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> list[TaskActivity]:
    _get_visible_task(session, task_id, user)
    return list(
        session.scalars(
            select(TaskActivity)
            .where(TaskActivity.task_id == task_id)
            .options(selectinload(TaskActivity.actor))
            .order_by(TaskActivity.created_at, TaskActivity.id)
        )
    )


@router.post("/{task_id}/comments", response_model=TaskTimelineEvent, status_code=status.HTTP_201_CREATED)
def add_task_comment(
    task_id: int,
    payload: TaskCommentRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> TaskActivity:
    task = _get_visible_task(session, task_id, user)
    comment = payload.comment.strip()
    if not comment:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Comment cannot be blank.")
    activity = record_task_activity(session, task, user, "COMMENTED", comment=comment)
    session.commit()
    return session.scalar(select(TaskActivity).options(selectinload(TaskActivity.actor)).where(TaskActivity.id == activity.id))


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
    updates = (
        ("title", task.title, _clean_title(payload.title)),
        ("description", task.description, payload.description.strip()),
        ("priority", task.priority.value, payload.priority.value),
        ("due date", task.due_date.isoformat() if task.due_date else None, payload.due_date.isoformat() if payload.due_date else None),
    )
    task.title = updates[0][2]
    task.description = updates[1][2]
    task.priority = payload.priority
    task.due_date = payload.due_date
    for field_name, previous_value, next_value in updates:
        if previous_value != next_value:
            if field_name == "due date":
                restore_task_alerts(session, task.id)
            record_task_activity(
                session, task, user, "FIELD_CHANGED", field_name=field_name, old_value=previous_value, new_value=next_value
            )
    _set_blockers(session, task, payload.blocker_ids, user)
    _set_assignees(session, task, payload.assignee_ids, user)
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
    record_task_activity(session, task, _, "DELETED")
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
