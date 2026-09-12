from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.services.security import hash_password


DEMO_USERS = (
    {"name": "Alice Morgan", "email": "alice@northstar.test", "password": "manager123", "role": UserRole.MANAGER},
    {"name": "Dan Chen", "email": "dan@northstar.test", "password": "member123", "role": UserRole.MEMBER},
)


def seed_demo_users(session: Session) -> None:
    for seed in DEMO_USERS:
        if session.scalar(select(User).where(User.email == seed["email"])):
            continue
        session.add(User(name=seed["name"], email=seed["email"], password_hash=hash_password(seed["password"]), role=seed["role"]))
    session.commit()


def authenticate(session: Session, email: str, password: str) -> User | None:
    user = session.scalar(select(User).where(User.email == email.lower().strip()))
    if not user or user.password_hash != hash_password(password):
        return None
    return user
