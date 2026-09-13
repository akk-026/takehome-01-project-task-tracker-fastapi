import unittest

from fastapi.testclient import TestClient

from app.main import app


class HealthCheckTests(unittest.TestCase):
    def test_health_check_returns_ok(self) -> None:
        with TestClient(app) as client:
            response = client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_vercel_rewrite_preserves_api_path(self) -> None:
        with TestClient(app) as client:
            response = client.get("/api/index.py?__northstar_path=api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
