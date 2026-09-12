from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_manager, get_db
from app.models.task import Task
from app.models.user import User

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    _: User = Depends(get_current_manager),
    session: Session = Depends(get_db),
) -> Response:
    task = session.get(Task, task_id)
    if not task or task.deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    task.deleted = True
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
