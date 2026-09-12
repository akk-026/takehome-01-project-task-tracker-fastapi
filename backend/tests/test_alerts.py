from datetime import date, timedelta
import unittest

from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.main import app


class OverdueAlertTests(unittest.TestCase):
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
                "name": "Operations",
                "owner_id": self.dan["user"]["id"],
                "member_ids": [self.dan["user"]["id"], self.priya["user"]["id"]],
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def create_task(self, project_id: int, title: str, due_date: date, assignee_ids: list[int]) -> dict:
        response = self.client.post(
            f"/api/tasks/projects/{project_id}",
            headers=self.headers(self.manager),
            json={"title": title, "due_date": due_date.isoformat(), "assignee_ids": assignee_ids},
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def alerts(self, session: dict) -> dict:
        response = self.client.get("/api/alerts", headers=self.headers(session))
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_assignees_receive_dismiss_and_restore_overdue_alerts(self) -> None:
        project = self.create_project()
        overdue = self.create_task(
            project["id"],
            "Send the overdue update",
            date.today() - timedelta(days=1),
            [self.dan["user"]["id"], self.priya["user"]["id"]],
        )
        not_due = self.create_task(
            project["id"], "Future work", date.today() + timedelta(days=1), [self.dan["user"]["id"]]
        )

        dan_alerts = self.alerts(self.dan)
        self.assertEqual(dan_alerts["count"], 1)
        self.assertEqual(dan_alerts["items"][0]["id"], overdue["id"])
        self.assertEqual(self.alerts(self.priya)["count"], 1)
        self.assertEqual(self.alerts(self.manager)["count"], 0)

        dismissed = self.client.post(f"/api/alerts/{overdue['id']}/dismiss", headers=self.headers(self.dan))
        self.assertEqual(dismissed.status_code, 204)
        self.assertEqual(self.alerts(self.dan)["count"], 0)
        self.assertEqual(self.alerts(self.priya)["count"], 1)
        self.assertEqual(
            self.client.post(f"/api/alerts/{overdue['id']}/dismiss", headers=self.headers(self.manager)).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(f"/api/alerts/{not_due['id']}/dismiss", headers=self.headers(self.dan)).status_code,
            422,
        )

        changed_due_date = date.today() - timedelta(days=2)
        updated = self.client.put(
            f"/api/tasks/{overdue['id']}",
            headers=self.headers(self.manager),
            json={
                "title": overdue["title"],
                "description": overdue["description"],
                "priority": overdue["priority"],
                "due_date": changed_due_date.isoformat(),
                "blocker_ids": overdue["blocker_ids"],
                "assignee_ids": overdue["assignee_ids"],
            },
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(self.alerts(self.dan)["count"], 1)
        self.assertEqual(self.alerts(self.priya)["count"], 1)

        self.assertEqual(
            self.client.post(f"/api/alerts/{overdue['id']}/dismiss", headers=self.headers(self.dan)).status_code,
            204,
        )
        bulk_changed = self.client.post(
            "/api/tasks/bulk",
            headers=self.headers(self.manager),
            json={
                "task_ids": [overdue["id"]],
                "action": "due_date",
                "due_date": (date.today() - timedelta(days=3)).isoformat(),
            },
        )
        self.assertEqual(bulk_changed.status_code, 200)
        self.assertEqual(self.alerts(self.dan)["count"], 1)

    def test_done_and_archived_project_tasks_do_not_appear_as_alerts(self) -> None:
        project = self.create_project()
        task = self.create_task(
            project["id"], "Finish the old task", date.today() - timedelta(days=1), [self.dan["user"]["id"]]
        )
        for target in ("IN_PROGRESS", "IN_REVIEW", "DONE"):
            response = self.client.post(
                f"/api/tasks/{task['id']}/status", headers=self.headers(self.dan), json={"status": target}
            )
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.alerts(self.dan)["count"], 0)

        archived_task = self.create_task(
            project["id"], "Archived overdue task", date.today() - timedelta(days=1), [self.dan["user"]["id"]]
        )
        self.assertEqual(self.alerts(self.dan)["count"], 1)
        archive = self.client.post(f"/api/projects/{project['id']}/archive", headers=self.headers(self.manager))
        self.assertEqual(archive.status_code, 200)
        self.assertEqual(self.alerts(self.dan)["count"], 0)
        self.assertEqual(
            self.client.post(f"/api/alerts/{archived_task['id']}/dismiss", headers=self.headers(self.dan)).status_code,
            404,
        )
