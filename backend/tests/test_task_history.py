import unittest

from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.main import app


class TaskHistoryTests(unittest.TestCase):
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

    def create_project(self, key: str, member_ids: list[int], owner_id: int | None = None) -> dict:
        response = self.client.post(
            "/api/projects",
            headers=self.headers(self.manager),
            json={"key": key, "name": f"{key} project", "owner_id": owner_id or self.dan["user"]["id"], "member_ids": member_ids},
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def create_task(self, project_id: int, payload: dict, session: dict | None = None) -> dict:
        response = self.client.post(
            f"/api/tasks/projects/{project_id}", headers=self.headers(session or self.manager), json=payload
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def timeline(self, task_id: int, session: dict | None = None) -> list[dict]:
        response = self.client.get(f"/api/tasks/{task_id}/timeline", headers=self.headers(session or self.manager))
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_timeline_records_creation_changes_assignments_status_and_comments(self) -> None:
        project = self.create_project("OPS", [self.dan["user"]["id"], self.priya["user"]["id"]])
        blocker = self.create_task(project["id"], {"title": "Write the brief"}, self.dan)
        task = self.create_task(
            project["id"],
            {"title": "Prepare launch", "assignee_ids": [self.dan["user"]["id"]]},
            self.dan,
        )

        updated = self.client.put(
            f"/api/tasks/{task['id']}",
            headers=self.headers(self.dan),
            json={
                "title": "Prepare client launch",
                "description": "Share the final timeline.",
                "priority": "HIGH",
                "due_date": "2030-12-31",
                "blocker_ids": [blocker["id"]],
                "assignee_ids": [self.priya["user"]["id"]],
            },
        )
        self.assertEqual(updated.status_code, 200)
        for target in ("IN_PROGRESS", "IN_REVIEW"):
            moved = self.client.post(
                f"/api/tasks/{task['id']}/status", headers=self.headers(self.priya), json={"status": target}
            )
            self.assertEqual(moved.status_code, 200)
        comment = self.client.post(
            f"/api/tasks/{task['id']}/comments",
            headers=self.headers(self.priya),
            json={"comment": "Ready for the client review."},
        )
        self.assertEqual(comment.status_code, 201)
        self.assertEqual(comment.json()["actor"]["name"], "Priya Shah")

        events = self.timeline(task["id"])
        self.assertEqual(events[0]["action"], "CREATED")
        self.assertEqual(events[0]["actor"]["name"], "Dan Chen")
        changes = {(event["field_name"], event["old_value"], event["new_value"]) for event in events if event["action"] == "FIELD_CHANGED"}
        self.assertIn(("title", "Prepare launch", "Prepare client launch"), changes)
        self.assertIn(("description", "", "Share the final timeline."), changes)
        self.assertIn(("priority", "MEDIUM", "HIGH"), changes)
        self.assertIn(("due date", None, "2030-12-31"), changes)
        self.assertIn(("blockers", None, "Write the brief"), changes)
        self.assertIn(("status", "BACKLOG", "IN_PROGRESS"), changes)
        self.assertIn(("status", "IN_PROGRESS", "IN_REVIEW"), changes)
        self.assertIn(("UNASSIGNED", "Dan Chen"), {(event["action"], event["old_value"]) for event in events})
        self.assertIn(("ASSIGNED", "Priya Shah"), {(event["action"], event["new_value"]) for event in events})
        self.assertEqual(events[-1]["action"], "COMMENTED")
        self.assertEqual(events[-1]["comment"], "Ready for the client review.")

        # There is deliberately no route that can rewrite a comment or historical event.
        self.assertEqual(
            self.client.put(
                f"/api/tasks/{task['id']}/comments/{comment.json()['id']}",
                headers=self.headers(self.manager),
                json={"comment": "Changed"},
            ).status_code,
            405,
        )
        self.assertEqual(self.timeline(task["id"])[-1]["comment"], "Ready for the client review.")
        self.assertEqual(
            self.client.post(
                f"/api/tasks/{task['id']}/comments", headers=self.headers(self.dan), json={"comment": "   "}
            ).status_code,
            422,
        )

    def test_membership_removal_logs_automatic_unassignment_and_visibility_is_enforced(self) -> None:
        project = self.create_project("OPS", [self.dan["user"]["id"], self.priya["user"]["id"]])
        task = self.create_task(project["id"], {"title": "Coordinate handoff", "assignee_ids": [self.priya["user"]["id"]]})
        removed = self.client.put(
            f"/api/projects/{project['id']}/members",
            headers=self.headers(self.manager),
            json={"member_ids": [self.dan["user"]["id"]]},
        )
        self.assertEqual(removed.status_code, 200)
        events = self.timeline(task["id"])
        self.assertEqual(events[-1]["action"], "UNASSIGNED")
        self.assertEqual(events[-1]["old_value"], "Priya Shah")
        self.assertEqual(events[-1]["actor"]["name"], "Alice Morgan")

        private_project = self.create_project("WEB", [self.priya["user"]["id"]], self.priya["user"]["id"])
        private_task = self.create_task(private_project["id"], {"title": "Private history"})
        self.assertEqual(self.client.get(f"/api/tasks/{private_task['id']}/timeline", headers=self.headers(self.dan)).status_code, 404)
        self.assertEqual(
            self.client.post(f"/api/tasks/{private_task['id']}/comments", headers=self.headers(self.dan), json={"comment": "No access"}).status_code,
            404,
        )
