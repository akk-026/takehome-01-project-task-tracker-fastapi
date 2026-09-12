from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.auth import UserResponse


class CreateProjectRequest(BaseModel):
    key: str = Field(min_length=2, max_length=12, pattern=r"^[A-Za-z0-9-]+$")
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2_000)
    owner_id: int
    member_ids: list[int] = Field(default_factory=list)


class ReplaceProjectMembersRequest(BaseModel):
    member_ids: list[int] = Field(default_factory=list)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    name: str
    description: str
    archived: bool
    owner: UserResponse
    members: list[UserResponse]
    created_at: datetime
    updated_at: datetime
