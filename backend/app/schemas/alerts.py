from pydantic import BaseModel

from app.schemas.tasks import AssignedTaskResponse


class AlertsResponse(BaseModel):
    items: list[AssignedTaskResponse]
    count: int
