import hashlib
import hmac
import secrets


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
