from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_current_user, get_db
from app.models.project import Project, project_members
from app.models.task import Task, TaskStatus
from app.models.user import User, UserRole
from app.schemas.dashboard import (
    AssigneeBreakdown,
    CompletionWeek,
    DashboardCounts,
    DashboardResponse,
    StatusBreakdown,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _visible_dashboard_tasks(session: Session, user: User) -> list[Task]:
    """Return active tasks only from projects the viewer is allowed to see."""
    statement = (
        select(Task)
        .join(Project)
        .options(selectinload(Task.assignees))
        .where(Task.deleted.is_(False), Project.archived.is_(False))
    )
    if user.role == UserRole.MEMBER:
        statement = statement.join(project_members).where(project_members.c.user_id == user.id)
    return list(session.scalars(statement).unique())


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> DashboardResponse:
    """Build a compact portfolio summary on the server for the current viewer."""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    next_week_start = week_start + timedelta(days=7)
    tasks = _visible_dashboard_tasks(session, user)

    open_tasks = [task for task in tasks if task.status != TaskStatus.DONE]
    counts = DashboardCounts(
        open_tasks=len(open_tasks),
        overdue_tasks=sum(task.due_date is not None and task.due_date < today for task in open_tasks),
        due_this_week=sum(
            task.due_date is not None and week_start <= task.due_date < next_week_start for task in open_tasks
        ),
        completed_this_week=sum(
            task.status == TaskStatus.DONE
            and task.completed_at is not None
            and week_start <= task.completed_at.date() < next_week_start
            for task in tasks
        ),
    )

    by_status = [
        StatusBreakdown(status=task_status, count=sum(task.status == task_status for task in tasks))
        for task_status in TaskStatus
    ]

    assignee_counts: dict[tuple[int | None, str], int] = {}
    for task in tasks:
        if task.assignees:
            for assignee in task.assignees:
                key = (assignee.id, assignee.name)
                assignee_counts[key] = assignee_counts.get(key, 0) + 1
        else:
            key = (None, "Unassigned")
            assignee_counts[key] = assignee_counts.get(key, 0) + 1
    by_assignee = [
        AssigneeBreakdown(user_id=user_id, name=name, count=count)
        for (user_id, name), count in sorted(assignee_counts.items(), key=lambda item: (item[0][0] is None, item[0][1]))
    ]

    eight_week_start = week_start - timedelta(weeks=7)
    completions = []
    for offset in range(8):
        bucket_start = eight_week_start + timedelta(weeks=offset)
        bucket_end = bucket_start + timedelta(days=7)
        completions.append(
            CompletionWeek(
                week_start=bucket_start,
                week_end=bucket_end - timedelta(days=1),
                completed=sum(
                    task.status == TaskStatus.DONE
                    and task.completed_at is not None
                    and bucket_start <= task.completed_at.date() < bucket_end
                    for task in tasks
                ),
            )
        )

    return DashboardResponse(counts=counts, by_status=by_status, by_assignee=by_assignee, completions=completions)
