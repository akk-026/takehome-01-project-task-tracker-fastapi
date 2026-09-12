from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.task_alert import TaskAlertDismissal


def restore_task_alerts(session: Session, task_id: int) -> None:
    """A changed deadline is a new alert condition, not a continuation of an old dismissal."""
    session.execute(delete(TaskAlertDismissal).where(TaskAlertDismissal.task_id == task_id))
