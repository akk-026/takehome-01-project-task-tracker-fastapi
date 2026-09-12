from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_current_manager, get_current_user, get_db
from app.models.project import Project, project_members
from app.models.task import Task, task_assignees
from app.models.user import User, UserRole
from app.services.task_history import record_task_activity
from app.schemas.projects import CreateProjectRequest, ProjectResponse, ReplaceProjectMembersRequest, UpdateProjectRequest

router = APIRouter(prefix="/projects", tags=["projects"])


def _project_query():
    return select(Project).options(selectinload(Project.owner), selectinload(Project.members))


def _get_visible_project(session: Session, project_id: int, user: User) -> Project:
    statement = _project_query().where(Project.id == project_id)
    if user.role == UserRole.MEMBER:
        statement = statement.join(project_members).where(project_members.c.user_id == user.id)
    project = session.scalar(statement)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


def _load_members(session: Session, member_ids: list[int], owner_id: int) -> list[User]:
    requested_ids = set(member_ids)
    requested_ids.add(owner_id)
    members = list(session.scalars(select(User).where(User.id.in_(requested_ids))))
    missing_ids = sorted(requested_ids - {member.id for member in members})
    if missing_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown user IDs: {missing_ids}.")
    return members


def _get_project_for_manager(session: Session, project_id: int) -> Project:
    project = session.scalar(_project_query().where(Project.id == project_id))
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


def _commit_project(session: Session, project: Project) -> Project:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Project key already exists.") from None
    return session.scalar(_project_query().where(Project.id == project.id))


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    include_archived: bool = Query(default=False),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[Project]:
    statement = _project_query().order_by(Project.key)
    if not include_archived:
        statement = statement.where(Project.archived.is_(False))
    if user.role == UserRole.MEMBER:
        statement = statement.join(project_members).where(project_members.c.user_id == user.id)
    return list(session.scalars(statement).unique())


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: CreateProjectRequest,
    _: User = Depends(get_current_manager),
    session: Session = Depends(get_db),
) -> Project:
    owner = session.get(User, payload.owner_id)
    if not owner:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Project owner does not exist.")
    project = Project(
        key=payload.key.upper(),
        name=payload.name.strip(),
        description=payload.description.strip(),
        owner=owner,
        members=_load_members(session, payload.member_ids, owner.id),
    )
    session.add(project)
    return _commit_project(session, project)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> Project:
    return _get_visible_project(session, project_id, user)


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    payload: UpdateProjectRequest,
    _: User = Depends(get_current_manager),
    session: Session = Depends(get_db),
) -> Project:
    project = _get_project_for_manager(session, project_id)
    owner = session.get(User, payload.owner_id)
    if not owner:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Project owner does not exist.")
    project.key = payload.key.upper()
    project.name = payload.name.strip()
    project.description = payload.description.strip()
    project.owner = owner
    if owner not in project.members:
        project.members.append(owner)
    return _commit_project(session, project)


@router.put("/{project_id}/members", response_model=ProjectResponse)
def replace_project_members(
    project_id: int,
    payload: ReplaceProjectMembersRequest,
    manager: User = Depends(get_current_manager),
    session: Session = Depends(get_db),
) -> Project:
    project = _get_project_for_manager(session, project_id)
    existing_member_ids = {member.id for member in project.members}
    members = _load_members(session, payload.member_ids, project.owner_id)
    removed_member_ids = existing_member_ids - {member.id for member in members}
    project.members = members
    if removed_member_ids:
        affected_tasks = list(
            session.scalars(
                select(Task)
                .join(task_assignees)
                .where(Task.project_id == project.id, task_assignees.c.user_id.in_(removed_member_ids))
                .options(selectinload(Task.assignees))
            ).unique()
        )
        for task in affected_tasks:
            for assignee in task.assignees:
                if assignee.id in removed_member_ids:
                    record_task_activity(
                        session,
                        task,
                        manager,
                        "UNASSIGNED",
                        field_name="assignee",
                        old_value=assignee.name,
                    )
        session.execute(
            delete(task_assignees).where(
                task_assignees.c.user_id.in_(removed_member_ids),
                task_assignees.c.task_id.in_(select(Task.id).where(Task.project_id == project.id)),
            )
        )
    return _commit_project(session, project)


@router.post("/{project_id}/archive", response_model=ProjectResponse)
def archive_project(
    project_id: int,
    _: User = Depends(get_current_manager),
    session: Session = Depends(get_db),
) -> Project:
    project = _get_project_for_manager(session, project_id)
    project.archived = True
    return _commit_project(session, project)


@router.post("/{project_id}/restore", response_model=ProjectResponse)
def restore_project(
    project_id: int,
    _: User = Depends(get_current_manager),
    session: Session = Depends(get_db),
) -> Project:
    project = _get_project_for_manager(session, project_id)
    project.archived = False
    return _commit_project(session, project)
