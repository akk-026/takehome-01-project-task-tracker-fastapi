from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_current_manager, get_current_user, get_db
from app.models.project import Project, project_members
from app.models.task import Task, task_blockers
from app.models.user import User, UserRole
from app.schemas.tasks import TaskResponse, TaskWriteRequest

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _task_query():
    return select(Task).options(selectinload(Task.blockers))


def _clean_title(title: str) -> str:
    clean_title = title.strip()
    if not clean_title:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Task title cannot be blank.")
    return clean_title


def _get_visible_project(session: Session, project_id: int, user: User) -> Project:
    statement = select(Project).where(Project.id == project_id)
    if user.role == UserRole.MEMBER:
        statement = statement.join(project_members).where(project_members.c.user_id == user.id)
    project = session.scalar(statement)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


def _get_visible_task(session: Session, task_id: int, user: User) -> Task:
    task = session.scalar(_task_query().where(Task.id == task_id, Task.deleted.is_(False)))
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    _get_visible_project(session, task.project_id, user)
    return task


def _set_blockers(session: Session, task: Task, blocker_ids: list[int]) -> None:
    requested_ids = set(blocker_ids)
    if task.id and task.id in requested_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="A task cannot block itself.")
    if not requested_ids:
        task.blockers = []
        return
    blockers = list(
        session.scalars(
            _task_query().where(
                Task.id.in_(requested_ids),
                Task.project_id == task.project_id,
                Task.deleted.is_(False),
            )
        )
    )
    found_ids = {blocker.id for blocker in blockers}
    if found_ids != requested_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Every blocker must be an active task in the same project.",
        )
    task.blockers = blockers


@router.get("/projects/{project_id}", response_model=list[TaskResponse])
def list_project_tasks(
    project_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[Task]:
    _get_visible_project(session, project_id, user)
    return list(session.scalars(_task_query().where(Task.project_id == project_id, Task.deleted.is_(False)).order_by(Task.updated_at.desc())))


@router.post("/projects/{project_id}", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    project_id: int,
    payload: TaskWriteRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Task:
    _get_visible_project(session, project_id, user)
    task = Task(
        project_id=project_id,
        title=_clean_title(payload.title),
        description=payload.description.strip(),
        priority=payload.priority,
        due_date=payload.due_date,
    )
    session.add(task)
    session.flush()
    _set_blockers(session, task, payload.blocker_ids)
    session.commit()
    return session.scalar(_task_query().where(Task.id == task.id))


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> Task:
    return _get_visible_task(session, task_id, user)


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    payload: TaskWriteRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Task:
    task = _get_visible_task(session, task_id, user)
    task.title = _clean_title(payload.title)
    task.description = payload.description.strip()
    task.priority = payload.priority
    task.due_date = payload.due_date
    _set_blockers(session, task, payload.blocker_ids)
    session.commit()
    return session.scalar(_task_query().where(Task.id == task.id))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    _: User = Depends(get_current_manager),
    session: Session = Depends(get_db),
) -> Response:
    task = session.get(Task, task_id)
    if not task or task.deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    session.execute(
        delete(task_blockers).where(
            or_(task_blockers.c.task_id == task.id, task_blockers.c.blocking_task_id == task.id)
        )
    )
    task.deleted = True
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
