from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_current_user, get_db
from app.models.project import Project, project_members
from app.models.task import Task, TaskStatus, task_assignees
from app.models.task_alert import TaskAlertDismissal
from app.models.user import User, UserRole
from app.schemas.alerts import AlertsResponse

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _overdue_alerts_statement(user: User):
    statement = (
        select(Task)
        .join(Project)
        .join(task_assignees)
        .outerjoin(
            TaskAlertDismissal,
            and_(TaskAlertDismissal.task_id == Task.id, TaskAlertDismissal.user_id == user.id),
        )
        .options(selectinload(Task.project), selectinload(Task.assignees))
        .where(
            task_assignees.c.user_id == user.id,
            Task.deleted.is_(False),
            Project.archived.is_(False),
            Task.due_date.is_not(None),
            Task.due_date < date.today(),
            Task.status != TaskStatus.DONE,
            TaskAlertDismissal.id.is_(None),
        )
        .order_by(Task.due_date, Task.id)
    )
    if user.role == UserRole.MEMBER:
        statement = statement.join(project_members).where(project_members.c.user_id == user.id)
    return statement


@router.get("", response_model=AlertsResponse)
def list_overdue_alerts(user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> AlertsResponse:
    tasks = list(session.scalars(_overdue_alerts_statement(user)).unique())
    return AlertsResponse(items=tasks, count=len(tasks))


@router.post("/{task_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_overdue_alert(
    task_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Response:
    statement = (
        select(Task)
        .join(Project)
        .options(selectinload(Task.assignees))
        .where(Task.id == task_id, Task.deleted.is_(False), Project.archived.is_(False))
    )
    if user.role == UserRole.MEMBER:
        statement = statement.join(project_members).where(project_members.c.user_id == user.id)
    task = session.scalar(statement)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    if user.id not in task.assignee_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an assigned person can dismiss this alert.")
    if task.status == TaskStatus.DONE or task.due_date is None or task.due_date >= date.today():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="This task does not have an active overdue alert.")
    existing = session.scalar(
        select(TaskAlertDismissal).where(TaskAlertDismissal.task_id == task.id, TaskAlertDismissal.user_id == user.id)
    )
    if not existing:
        session.add(TaskAlertDismissal(task_id=task.id, user_id=user.id))
        session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
