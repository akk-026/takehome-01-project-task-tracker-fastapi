from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_current_manager, get_current_user, get_db
from app.models.project import Project, project_members
from app.models.user import User, UserRole
from app.schemas.projects import CreateProjectRequest, ProjectResponse, ReplaceProjectMembersRequest

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
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Project key already exists.") from None
    return session.scalar(_project_query().where(Project.id == project.id))


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> Project:
    return _get_visible_project(session, project_id, user)


@router.put("/{project_id}/members", response_model=ProjectResponse)
def replace_project_members(
    project_id: int,
    payload: ReplaceProjectMembersRequest,
    _: User = Depends(get_current_manager),
    session: Session = Depends(get_db),
) -> Project:
    project = session.scalar(_project_query().where(Project.id == project_id))
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    project.members = _load_members(session, payload.member_ids, project.owner_id)
    session.commit()
    return session.scalar(_project_query().where(Project.id == project.id))


@router.post("/{project_id}/archive", response_model=ProjectResponse)
def archive_project(
    project_id: int,
    _: User = Depends(get_current_manager),
    session: Session = Depends(get_db),
) -> Project:
    project = session.scalar(_project_query().where(Project.id == project_id))
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    project.archived = True
    session.commit()
    return session.scalar(_project_query().where(Project.id == project.id))

