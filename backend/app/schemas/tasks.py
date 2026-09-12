from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.task import TaskPriority


class TaskWriteRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=4_000)
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: date | None = None
    blocker_ids: list[int] = Field(default_factory=list)


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    description: str
    priority: TaskPriority
    due_date: date | None
    blocker_ids: list[int]
    created_at: datetime
    updated_at: datetime
