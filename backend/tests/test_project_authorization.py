import unittest

from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models.task import Task


class ProjectAuthorizationTests(unittest.TestCase):
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

    def create_project(self) -> dict:
        response = self.client.post(
            "/api/projects",
            headers=self.headers(self.manager),
            json={
                "key": "OPS",
                "name": "Operations refresh",
                "description": "A private project for Dan.",
                "owner_id": self.dan["user"]["id"],
                "member_ids": [self.dan["user"]["id"]],
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_member_sees_only_projects_they_belong_to(self) -> None:
        project = self.create_project()

        self.assertEqual(self.client.get("/api/projects", headers=self.headers(self.dan)).json()[0]["id"], project["id"])
        self.assertEqual(self.client.get("/api/projects", headers=self.headers(self.priya)).json(), [])
        self.assertEqual(self.client.get(f"/api/projects/{project['id']}", headers=self.headers(self.priya)).status_code, 404)

    def test_member_cannot_mutate_projects_or_delete_tasks(self) -> None:
        project = self.create_project()
        with SessionLocal() as database:
            task = Task(project_id=project["id"], title="Do the work")
            database.add(task)
            database.commit()
            database.refresh(task)
            task_id = task.id

        member_headers = self.headers(self.dan)
        self.assertEqual(self.client.post("/api/projects", headers=member_headers, json={"key": "NO", "name": "No", "owner_id": self.dan["user"]["id"]}).status_code, 403)
        self.assertEqual(self.client.put(f"/api/projects/{project['id']}", headers=member_headers, json={"key": "NO", "name": "No", "owner_id": self.dan["user"]["id"]}).status_code, 403)
        self.assertEqual(self.client.put(f"/api/projects/{project['id']}/members", headers=member_headers, json={"member_ids": []}).status_code, 403)
        self.assertEqual(self.client.post(f"/api/projects/{project['id']}/archive", headers=member_headers).status_code, 403)
        self.assertEqual(self.client.post(f"/api/projects/{project['id']}/restore", headers=member_headers).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/tasks/{task_id}", headers=member_headers).status_code, 403)
        self.assertEqual(self.client.get("/api/users", headers=member_headers).status_code, 403)

    def test_manager_can_change_members_archive_and_delete_task(self) -> None:
        project = self.create_project()
        with SessionLocal() as database:
            task = Task(project_id=project["id"], title="Do the work")
            database.add(task)
            database.commit()
            database.refresh(task)
            task_id = task.id

        manager_headers = self.headers(self.manager)
        member_update = self.client.put(
            f"/api/projects/{project['id']}/members",
            headers=manager_headers,
            json={"member_ids": [self.priya["user"]["id"]]},
        )
        self.assertEqual(member_update.status_code, 200)
        self.assertEqual({member["id"] for member in member_update.json()["members"]}, {self.dan["user"]["id"], self.priya["user"]["id"]})
        self.assertTrue(self.client.post(f"/api/projects/{project['id']}/archive", headers=manager_headers).json()["archived"])
        self.assertEqual(self.client.delete(f"/api/tasks/{task_id}", headers=manager_headers).status_code, 204)

    def test_manager_can_edit_restore_and_preserve_archived_project_data(self) -> None:
        project = self.create_project()
        with SessionLocal() as database:
            task = Task(project_id=project["id"], title="Keep this task")
            database.add(task)
            database.commit()
            database.refresh(task)
            task_id = task.id

        manager_headers = self.headers(self.manager)
        edited = self.client.put(
            f"/api/projects/{project['id']}",
            headers=manager_headers,
            json={
                "key": "PLAT",
                "name": "Platform refresh",
                "description": "Updated scope.",
                "owner_id": self.priya["user"]["id"],
            },
        )
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json()["key"], "PLAT")
        self.assertEqual(edited.json()["owner"]["id"], self.priya["user"]["id"])
        self.assertEqual({member["id"] for member in edited.json()["members"]}, {self.dan["user"]["id"], self.priya["user"]["id"]})

        self.assertTrue(self.client.post(f"/api/projects/{project['id']}/archive", headers=manager_headers).json()["archived"])
        self.assertEqual(self.client.get("/api/projects", headers=manager_headers).json(), [])
        self.assertEqual(self.client.get("/api/projects?include_archived=true", headers=manager_headers).json()[0]["id"], project["id"])
        with SessionLocal() as database:
            self.assertEqual(database.get(Task, task_id).title, "Keep this task")

        restored = self.client.post(f"/api/projects/{project['id']}/restore", headers=manager_headers)
        self.assertEqual(restored.status_code, 200)
        self.assertFalse(restored.json()["archived"])
        self.assertEqual(self.client.get("/api/projects", headers=manager_headers).json()[0]["id"], project["id"])
