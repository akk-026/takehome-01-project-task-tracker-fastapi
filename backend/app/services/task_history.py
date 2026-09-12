from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.task_activity import TaskActivity
from app.models.user import User


def record_task_activity(
    session: Session,
    task: Task,
    actor: User | None,
    action: str,
    *,
    field_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    comment: str | None = None,
) -> TaskActivity:
    """Append one immutable event; no code path updates or deletes these records."""
    activity = TaskActivity(
        task=task,
        actor=actor,
        action=action,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        comment=comment,
    )
    session.add(activity)
    return activity
