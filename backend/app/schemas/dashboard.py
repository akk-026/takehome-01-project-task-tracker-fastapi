from datetime import date

from pydantic import BaseModel

from app.models.task import TaskStatus


class DashboardCounts(BaseModel):
    open_tasks: int
    overdue_tasks: int
    due_this_week: int
    completed_this_week: int


class StatusBreakdown(BaseModel):
    status: TaskStatus
    count: int


class AssigneeBreakdown(BaseModel):
    user_id: int | None = None
    name: str
    count: int


class CompletionWeek(BaseModel):
    week_start: date
    week_end: date
    completed: int


class DashboardResponse(BaseModel):
    counts: DashboardCounts
    by_status: list[StatusBreakdown]
    by_assignee: list[AssigneeBreakdown]
    completions: list[CompletionWeek]
