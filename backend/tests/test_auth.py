import unittest

from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.main import app
from app.models.user import User


class AuthenticationTests(unittest.TestCase):
    def setUp(self) -> None:
        # Each test starts with an empty database; the app lifespan seeds demo accounts.
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)

    def login(self, email: str, password: str) -> dict:
        response = self.client.post("/api/auth/login", json={"email": email, "password": password})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_manager_can_sign_in_without_receiving_password_hash(self) -> None:
        session = self.login("alice@northstar.test", "manager123")
        self.assertEqual(session["user"]["role"], "MANAGER")
        self.assertNotIn("password_hash", session["user"])
        self.assertTrue(session["token"])

    def test_invalid_credentials_and_missing_session_are_rejected(self) -> None:
        invalid = self.client.post("/api/auth/login", json={"email": "alice@northstar.test", "password": "wrong"})
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_member_cannot_pass_server_side_manager_check(self) -> None:
        member = self.login("dan@northstar.test", "member123")
        denied = self.client.post("/api/auth/manager-check", headers={"authorization": f"Bearer {member['token']}"})
        self.assertEqual(denied.status_code, 403)
        self.assertIn("server", denied.json()["detail"])

    def test_logout_invalidates_the_session(self) -> None:
        manager = self.login("alice@northstar.test", "manager123")
        headers = {"authorization": f"Bearer {manager['token']}"}
        self.assertEqual(self.client.post("/api/auth/logout", headers=headers).status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 401)

    def test_session_remains_valid_for_a_new_client(self) -> None:
        manager = self.login("alice@northstar.test", "manager123")
        headers = {"authorization": f"Bearer {manager['token']}"}
        with TestClient(app) as another_client:
            response = another_client.get("/api/auth/me", headers=headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "alice@northstar.test")
