from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_manager, get_db
from app.models.user import User
from app.schemas.auth import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
def list_users(_: User = Depends(get_current_manager), session: Session = Depends(get_db)) -> list[User]:
    return list(session.scalars(select(User).order_by(User.name)))
