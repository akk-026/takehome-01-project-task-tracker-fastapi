from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.api.dependencies import bearer_scheme, get_current_manager, get_current_user, get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, UserResponse
from app.services.security import session_store
from app.services.users import authenticate

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, session: Session = Depends(get_db)) -> LoginResponse:
    user = authenticate(session, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password.")
    return LoginResponse(token=session_store.create(user.id), user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme), _: User = Depends(get_current_user)) -> None:
    if credentials:
        session_store.remove(credentials.credentials)


@router.post("/manager-check")
def manager_check(_: User = Depends(get_current_manager)) -> dict[str, bool]:
    return {"ok": True}
