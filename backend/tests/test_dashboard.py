from datetime import date, datetime, time, timedelta, timezone
import unittest

from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models.task import Task


class DashboardTests(unittest.TestCase):
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
            json={"key": key, "name": f"{key} project", "owner_id": owner_id, "member_ids": member_ids},
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def create_task(self, project_id: int, title: str, **extra: object) -> dict:
        response = self.client.post(
            f"/api/tasks/projects/{project_id}",
            headers=self.headers(self.manager),
            json={"title": title, **extra},
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def complete_task(self, task_id: int) -> None:
        for target in ("IN_PROGRESS", "IN_REVIEW", "DONE"):
            response = self.client.post(
                f"/api/tasks/{task_id}/status",
                headers=self.headers(self.manager),
                json={"status": target},
            )
            self.assertEqual(response.status_code, 200)

    def set_completed_at(self, task_id: int, completed_on: date) -> None:
        with SessionLocal() as session:
            task = session.get(Task, task_id)
            task.completed_at = datetime.combine(completed_on, time.min, tzinfo=timezone.utc)
            session.commit()

    def test_dashboard_aggregates_active_visible_tasks_and_completion_weeks(self) -> None:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        shared = self.create_project(
            "OPS", self.dan["user"]["id"], [self.dan["user"]["id"], self.priya["user"]["id"]]
        )
        private = self.create_project("WEB", self.priya["user"]["id"], [self.priya["user"]["id"]])
        overdue = self.create_task(
            shared["id"], "Overdue launch brief", due_date=(today - timedelta(days=1)).isoformat(), assignee_ids=[self.dan["user"]["id"]]
        )
        self.create_task(
            shared["id"], "This week's review", due_date=today.isoformat(), assignee_ids=[self.priya["user"]["id"]]
        )
        self.create_task(shared["id"], "Unassigned follow-up")
        shared_done = self.create_task(shared["id"], "Shared completed work", assignee_ids=[self.dan["user"]["id"]])
        private_done = self.create_task(private["id"], "Private completed work", assignee_ids=[self.priya["user"]["id"]])
        self.complete_task(shared_done["id"])
        self.complete_task(private_done["id"])
        self.set_completed_at(shared_done["id"], week_start)
        self.set_completed_at(private_done["id"], week_start - timedelta(weeks=2))

        manager_dashboard = self.client.get("/api/dashboard", headers=self.headers(self.manager))
        self.assertEqual(manager_dashboard.status_code, 200)
        manager_data = manager_dashboard.json()
        self.assertEqual(
            manager_data["counts"],
            {"open_tasks": 3, "overdue_tasks": 1, "due_this_week": 2, "completed_this_week": 1},
        )
        self.assertEqual({row["status"]: row["count"] for row in manager_data["by_status"]}["BACKLOG"], 3)
        self.assertEqual({row["status"]: row["count"] for row in manager_data["by_status"]}["DONE"], 2)
        assignees = {row["name"]: row["count"] for row in manager_data["by_assignee"]}
        self.assertEqual(assignees, {"Dan Chen": 2, "Priya Shah": 2, "Unassigned": 1})
        self.assertEqual(len(manager_data["completions"]), 8)
        self.assertEqual(manager_data["completions"][-1]["completed"], 1)
        self.assertEqual(manager_data["completions"][-3]["completed"], 1)

        member_dashboard = self.client.get("/api/dashboard", headers=self.headers(self.dan))
        self.assertEqual(member_dashboard.status_code, 200)
        member_data = member_dashboard.json()
        self.assertEqual(
            member_data["counts"],
            {"open_tasks": 3, "overdue_tasks": 1, "due_this_week": 2, "completed_this_week": 1},
        )
        self.assertEqual({row["status"]: row["count"] for row in member_data["by_status"]}["DONE"], 1)
        self.assertNotIn("Private completed work", str(member_data))

        # A task completed through the lifecycle receives a durable completion timestamp.
        completed_task = self.client.get(f"/api/tasks/{shared_done['id']}", headers=self.headers(self.manager)).json()
        self.assertIsNotNone(completed_task["completed_at"])
        self.assertEqual(overdue["status"], "BACKLOG")
