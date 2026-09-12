import hashlib
import secrets


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class SessionStore:
    """In-memory opaque sessions. A persistent auth provider is outside this take-home's scope."""

    def __init__(self) -> None:
        self._sessions: dict[str, int] = {}

    def create(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        self._sessions[token] = user_id
        return token

    def user_id_for(self, token: str) -> int | None:
        return self._sessions.get(token)

    def remove(self, token: str) -> None:
        self._sessions.pop(token, None)


session_store = SessionStore()
