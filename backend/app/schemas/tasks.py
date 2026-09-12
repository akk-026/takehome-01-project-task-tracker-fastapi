from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.task import TaskPriority, TaskStatus


class TaskWriteRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=4_000)
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: date | None = None
    blocker_ids: list[int] = Field(default_factory=list)
    assignee_ids: list[int] = Field(default_factory=list)


class TaskStatusChangeRequest(BaseModel):
    status: TaskStatus


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    description: str
    priority: TaskPriority
    due_date: date | None
    status: TaskStatus
    blocked_from: TaskStatus | None
    blocker_ids: list[int]
    assignee_ids: list[int]
    available_statuses: list[TaskStatus]
    created_at: datetime
    updated_at: datetime


class AssignedTaskResponse(TaskResponse):
    project_key: str
    project_name: str


class TaskSearchResponse(BaseModel):
    items: list[AssignedTaskResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class TaskBulkUpdateRequest(BaseModel):
    task_ids: list[int] = Field(min_length=1, max_length=100)
    action: Literal["status", "assignees", "due_date"]
    status: TaskStatus | None = None
    assignee_ids: list[int] = Field(default_factory=list)
    due_date: date | None = None


class BulkTaskResult(BaseModel):
    task_id: int
    succeeded: bool
    detail: str
    task: TaskResponse | None = None


class BulkTaskUpdateResponse(BaseModel):
    results: list[BulkTaskResult]
    succeeded: int
    rejected: int
