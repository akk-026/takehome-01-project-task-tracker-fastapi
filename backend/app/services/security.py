import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.user_session import UserSession


SESSION_LIFETIME = timedelta(days=7)


def hash_password(password: str) -> str:
    """Create a salted password hash using only the standard library."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)
    return f"pbkdf2_sha256$600000${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify new PBKDF2 hashes and the previous demo hash format during migration."""
    algorithm, *parts = stored_hash.split("$")
    if algorithm == "pbkdf2_sha256" and len(parts) == 3:
        iterations, salt_hex, expected_digest = parts
        try:
            candidate = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
            ).hex()
        except (TypeError, ValueError):
            return False
        return hmac.compare_digest(candidate, expected_digest)
    return hmac.compare_digest(hashlib.sha256(password.encode("utf-8")).hexdigest(), stored_hash)


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(session: Session, user_id: int) -> str:
    """Persist an opaque token so a request can land on any serverless instance."""
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    session.execute(delete(UserSession).where(UserSession.expires_at <= now))
    session.add(
        UserSession(
            token_digest=_token_digest(token),
            user_id=user_id,
            expires_at=now + SESSION_LIFETIME,
        )
    )
    session.commit()
    return token


def session_user_id(session: Session, token: str) -> int | None:
    now = datetime.now(timezone.utc)
    return session.scalar(
        select(UserSession.user_id).where(
            UserSession.token_digest == _token_digest(token),
            UserSession.expires_at > now,
        )
    )


def remove_session(session: Session, token: str) -> None:
    session.execute(delete(UserSession).where(UserSession.token_digest == _token_digest(token)))
    session.commit()
