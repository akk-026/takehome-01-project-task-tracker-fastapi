import unittest

from fastapi.testclient import TestClient

from app.main import app


class HealthCheckTests(unittest.TestCase):
    def test_health_check_returns_ok(self) -> None:
        with TestClient(app) as client:
            response = client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
