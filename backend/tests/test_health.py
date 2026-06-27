"""Slice 1 smoke test: the app starts and /health responds.

This test does not require a running MySQL — it asserts the route works and
that the DB status is one of the two valid values, so it is CI-safe.
"""

from fastapi.testclient import TestClient

from backend.main import app


def test_health_endpoint():
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["database"] in {"connected", "disconnected"}
