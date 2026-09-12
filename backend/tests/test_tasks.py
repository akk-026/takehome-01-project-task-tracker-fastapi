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

    def move_task(self, task_id: int, status: str, session: dict | None = None) -> dict:
        response = self.client.post(
            f"/api/tasks/{task_id}/status",
            headers=self.headers(session or self.manager),
            json={"status": status},
        )
        self.assertEqual(response.status_code, 200)
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

    def test_task_lifecycle_only_allows_legal_moves_and_respects_blockers(self) -> None:
        project = self.create_project("OPS", self.dan["user"]["id"], [self.dan["user"]["id"]])
        blocker = self.create_task(project["id"], {"title": "Finish research"})
        task = self.create_task(project["id"], {"title": "Publish proposal", "blocker_ids": [blocker["id"]]})

        invalid_jump = self.client.post(
            f"/api/tasks/{task['id']}/status",
            headers=self.headers(self.dan),
            json={"status": "DONE"},
        )
        self.assertEqual(invalid_jump.status_code, 422)
        self.assertIn("Backlog", invalid_jump.json()["detail"])
        self.assertIn("In Progress", invalid_jump.json()["detail"])

        in_progress = self.move_task(task["id"], "IN_PROGRESS", self.dan)
        self.assertEqual(in_progress["status"], "IN_PROGRESS")
        self.assertEqual(in_progress["available_statuses"], ["IN_REVIEW", "BLOCKED"])
        in_review = self.move_task(task["id"], "IN_REVIEW", self.dan)
        self.assertEqual(in_review["available_statuses"], ["BLOCKED"])

        unfinished_blocker = self.client.post(
            f"/api/tasks/{task['id']}/status",
            headers=self.headers(self.dan),
            json={"status": "DONE"},
        )
        self.assertEqual(unfinished_blocker.status_code, 422)
        self.assertIn("unfinished blocking tasks", unfinished_blocker.json()["detail"])

        self.move_task(blocker["id"], "IN_PROGRESS", self.dan)
        self.move_task(blocker["id"], "IN_REVIEW", self.dan)
        self.move_task(blocker["id"], "DONE", self.dan)

        ready_to_finish = self.client.get(f"/api/tasks/{task['id']}", headers=self.headers(self.dan)).json()
        self.assertEqual(ready_to_finish["available_statuses"], ["DONE", "BLOCKED"])
        blocked = self.move_task(task["id"], "BLOCKED", self.dan)
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertEqual(blocked["blocked_from"], "IN_REVIEW")
        self.assertEqual(blocked["available_statuses"], ["IN_REVIEW"])
        unblocked = self.move_task(task["id"], "IN_REVIEW", self.dan)
        self.assertEqual(unblocked["status"], "IN_REVIEW")
        self.assertIsNone(unblocked["blocked_from"])

        completed = self.move_task(task["id"], "DONE", self.dan)
        self.assertEqual(completed["status"], "DONE")
        self.assertEqual(completed["available_statuses"], ["IN_PROGRESS"])
        reopened = self.move_task(task["id"], "IN_PROGRESS", self.dan)
        self.assertEqual(reopened["status"], "IN_PROGRESS")

    def test_assignments_require_project_membership_and_are_removed_with_membership(self) -> None:
        project = self.create_project(
            "OPS",
            self.dan["user"]["id"],
            [self.dan["user"]["id"], self.priya["user"]["id"]],
        )
        task = self.create_task(
            project["id"],
            {"title": "Coordinate launch", "assignee_ids": [self.priya["user"]["id"]]},
            self.dan,
        )
        self.assertEqual(task["assignee_ids"], [self.priya["user"]["id"]])

        updated = self.client.put(
            f"/api/tasks/{task['id']}",
            headers=self.headers(self.dan),
            json={
                "title": "Coordinate launch",
                "description": "Keep the launch team aligned.",
                "priority": "HIGH",
                "due_date": None,
                "blocker_ids": [],
                "assignee_ids": [self.dan["user"]["id"], self.priya["user"]["id"]],
            },
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(
            updated.json()["assignee_ids"],
            [self.dan["user"]["id"], self.priya["user"]["id"]],
        )

        second_task = self.create_task(
            project["id"],
            {"title": "Share the brief", "assignee_ids": [self.dan["user"]["id"]]},
            self.dan,
        )

        dan_assigned = self.client.get("/api/tasks/assigned", headers=self.headers(self.dan))
        self.assertEqual(dan_assigned.status_code, 200)
        self.assertEqual({assigned["id"] for assigned in dan_assigned.json()}, {task["id"], second_task["id"]})
        self.assertTrue(all(assigned["project_key"] == project["key"] for assigned in dan_assigned.json()))

        invalid_assignee = self.client.post(
            f"/api/tasks/projects/{project['id']}",
            headers=self.headers(self.dan),
            json={"title": "Invalid assignment", "assignee_ids": [self.manager["user"]["id"]]},
        )
        self.assertEqual(invalid_assignee.status_code, 422)
        self.assertIn("member", invalid_assignee.json()["detail"])

        removed = self.client.put(
            f"/api/projects/{project['id']}/members",
            headers=self.headers(self.manager),
            json={"member_ids": [self.dan["user"]["id"]]},
        )
        self.assertEqual(removed.status_code, 200)
        refreshed_task = self.client.get(f"/api/tasks/{task['id']}", headers=self.headers(self.manager)).json()
        self.assertEqual(refreshed_task["assignee_ids"], [self.dan["user"]["id"]])
        self.assertEqual(
            {assigned["id"] for assigned in self.client.get("/api/tasks/assigned", headers=self.headers(self.dan)).json()},
            {task["id"], second_task["id"]},
        )
        self.assertEqual(self.client.get("/api/tasks/assigned", headers=self.headers(self.priya)).json(), [])
