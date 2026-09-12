from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlalchemy import Boolean, Column, Date, DateTime, Enum as SqlEnum, ForeignKey, String, Table, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TaskPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TaskStatus(str, Enum):
    BACKLOG = "BACKLOG"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW = "IN_REVIEW"
    BLOCKED = "BLOCKED"
    DONE = "DONE"


task_blockers = Table(
    "task_blockers",
    Base.metadata,
    Column("task_id", ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("blocking_task_id", ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
)


task_assignees = Table(
    "task_assignees",
    Base.metadata,
    Column("task_id", ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)


class Task(Base):

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(String(4_000), default="", server_default="")
    priority: Mapped[TaskPriority] = mapped_column(SqlEnum(TaskPriority), default=TaskPriority.MEDIUM, server_default=TaskPriority.MEDIUM.value)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(SqlEnum(TaskStatus), default=TaskStatus.BACKLOG, server_default=TaskStatus.BACKLOG.value)
    blocked_from: Mapped[TaskStatus | None] = mapped_column(SqlEnum(TaskStatus), nullable=True)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    blockers = relationship(
        "Task",
        secondary=task_blockers,
        primaryjoin=id == task_blockers.c.task_id,
        secondaryjoin=id == task_blockers.c.blocking_task_id,
    )
    assignees = relationship("User", secondary=task_assignees)
    project = relationship("Project")

    @property
    def blocker_ids(self) -> list[int]:
        return [blocker.id for blocker in self.blockers]

    @property
    def assignee_ids(self) -> list[int]:
        return sorted(assignee.id for assignee in self.assignees)

    @property
    def project_key(self) -> str:
        return self.project.key

    @property
    def project_name(self) -> str:
        return self.project.name

    @property
    def available_statuses(self) -> list[TaskStatus]:
        """Return only lifecycle moves that are legal for this task right now."""
        if self.status == TaskStatus.BACKLOG:
            return [TaskStatus.IN_PROGRESS]
        if self.status == TaskStatus.IN_PROGRESS:
            return [TaskStatus.IN_REVIEW, TaskStatus.BLOCKED]
        if self.status == TaskStatus.IN_REVIEW:
            transitions = [TaskStatus.BLOCKED]
            if all(blocker.status == TaskStatus.DONE for blocker in self.blockers):
                transitions.insert(0, TaskStatus.DONE)
            return transitions
        if self.status == TaskStatus.BLOCKED:
            return [self.blocked_from] if self.blocked_from else []
        if self.status == TaskStatus.DONE:
            return [TaskStatus.IN_PROGRESS]
        return []
