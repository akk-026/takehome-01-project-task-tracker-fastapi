import unittest

from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.main import app


class TaskTests(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()
        self.manager = self.login("alice@northstar.test", "manager123")
        self.dan = self.login("dan@northstar.test", "member123")
        self.priya = self.login("priya@northstar.test", "member123")

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)

    def login(self, email: str, password: str) -> dict:
        response = self.client.post("/api/auth/login", json={"email": email, "password": password})
        self.assertEqual(response.status_code, 200)
        return response.json()

    @staticmethod
    def headers(session: dict) -> dict[str, str]:
        return {"authorization": f"Bearer {session['token']}"}

    def create_project(self, key: str, owner_id: int, member_ids: list[int]) -> dict:
        response = self.client.post(
            "/api/projects",
            headers=self.headers(self.manager),
            json={"key": key, "name": f"{key} project", "description": "Project tasks live here.", "owner_id": owner_id, "member_ids": member_ids},
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def create_task(self, project_id: int, payload: dict, session: dict | None = None) -> dict:
        response = self.client.post(
            f"/api/tasks/projects/{project_id}",
            headers=self.headers(session or self.manager),
            json=payload,
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_project_member_can_create_edit_and_view_project_tasks(self) -> None:
        project = self.create_project("OPS", self.dan["user"]["id"], [self.dan["user"]["id"]])
        first = self.create_task(
            project["id"],
            {"title": "  Gather requirements  ", "description": "Confirm the rollout scope.", "priority": "HIGH", "due_date": "2026-10-03"},
            self.dan,
        )
        self.assertEqual(first["title"], "Gather requirements")
        self.assertEqual(first["priority"], "HIGH")
        self.assertEqual(first["due_date"], "2026-10-03")

        second = self.create_task(
            project["id"],
            {"title": "Publish rollout", "description": "Ship once scope is clear.", "priority": "CRITICAL", "blocker_ids": [first["id"]]},
            self.dan,
        )
        self.assertEqual(second["blocker_ids"], [first["id"]])
        project_tasks = self.client.get(f"/api/tasks/projects/{project['id']}", headers=self.headers(self.dan))
        self.assertEqual(project_tasks.status_code, 200)
        self.assertEqual({task["id"] for task in project_tasks.json()}, {first["id"], second["id"]})

        edited = self.client.put(
            f"/api/tasks/{second['id']}",
            headers=self.headers(self.dan),
            json={"title": "Publish the rollout", "description": "Ready for release.", "priority": "MEDIUM", "due_date": None, "blocker_ids": []},
        )
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json()["title"], "Publish the rollout")
        self.assertEqual(edited.json()["blocker_ids"], [])

    def test_blockers_must_be_other_active_tasks_in_the_same_project(self) -> None:
        first_project = self.create_project("OPS", self.dan["user"]["id"], [self.dan["user"]["id"]])
        second_project = self.create_project("WEB", self.priya["user"]["id"], [self.priya["user"]["id"]])
        first_task = self.create_task(first_project["id"], {"title": "First task"})
        external_task = self.create_task(second_project["id"], {"title": "External task"})

        self.assertEqual(self.client.get(f"/api/tasks/projects/{second_project['id']}", headers=self.headers(self.dan)).status_code, 404)
        self.assertEqual(self.client.post(f"/api/tasks/projects/{second_project['id']}", headers=self.headers(self.dan), json={"title": "Not allowed"}).status_code, 404)

        cross_project = self.client.post(
            f"/api/tasks/projects/{first_project['id']}",
            headers=self.headers(self.manager),
            json={"title": "Invalid blocker", "blocker_ids": [external_task["id"]]},
        )
        self.assertEqual(cross_project.status_code, 422)
        self.assertIn("same project", cross_project.json()["detail"])

        self_blocking = self.client.put(
            f"/api/tasks/{first_task['id']}",
            headers=self.headers(self.manager),
            json={"title": "First task", "blocker_ids": [first_task["id"]]},
        )
        self.assertEqual(self_blocking.status_code, 422)
        self.assertIn("itself", self_blocking.json()["detail"])

    def test_manager_delete_hides_task_without_deleting_project(self) -> None:
        project = self.create_project("OPS", self.dan["user"]["id"], [self.dan["user"]["id"]])
        task = self.create_task(project["id"], {"title": "Delete me"})
        dependent_task = self.create_task(project["id"], {"title": "Keep me", "blocker_ids": [task["id"]]})

        self.assertEqual(self.client.delete(f"/api/tasks/{task['id']}", headers=self.headers(self.manager)).status_code, 204)
        tasks = self.client.get(f"/api/tasks/projects/{project['id']}", headers=self.headers(self.manager)).json()
        self.assertEqual(tasks[0]["id"], dependent_task["id"])
        self.assertEqual(tasks[0]["blocker_ids"], [])
        self.assertEqual(self.client.get(f"/api/projects/{project['id']}", headers=self.headers(self.manager)).status_code, 200)
