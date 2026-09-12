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


task_blockers = Table(
    "task_blockers",
    Base.metadata,
    Column("task_id", ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("blocking_task_id", ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
)


class Task(Base):

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(String(4_000), default="", server_default="")
    priority: Mapped[TaskPriority] = mapped_column(SqlEnum(TaskPriority), default=TaskPriority.MEDIUM, server_default=TaskPriority.MEDIUM.value)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    blockers = relationship(
        "Task",
        secondary=task_blockers,
        primaryjoin=id == task_blockers.c.task_id,
        secondaryjoin=id == task_blockers.c.blocking_task_id,
    )

    @property
    def blocker_ids(self) -> list[int]:
        return [blocker.id for blocker in self.blockers]
