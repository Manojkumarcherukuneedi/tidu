"""Shared pytest fixtures that make the whole suite hermetic.

Two external dependencies are stubbed so the suite runs offline, for free, and
with no setup — which is exactly what a reviewer or CI needs:

  1. The LLM (`ai_service._call_llm`) is blocked by default via an autouse
     fixture, so NO test can ever reach the real Anthropic API (even by
     accident). Tests that want a specific model response override it.

  2. The database (`crud.*`) is replaced with an in-memory store, so route
     tests exercise the real FastAPI routes + validation + 404 handling +
     enrichment merge without needing a running MySQL.

`database.init_db` is also no-op'd so the app's startup lifespan doesn't try to
connect to MySQL when the TestClient boots.
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend import ai_service, crud, database
from backend.main import app
from backend.models import TaskCreate, TaskUpdate


def _blocked_llm(*_args, **_kwargs):
    raise RuntimeError("LLM call blocked in tests (no real API call allowed)")


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    """Applied to every test: no real LLM, no DB bootstrap on startup."""
    monkeypatch.setattr(ai_service, "_call_llm", _blocked_llm)
    monkeypatch.setattr(database, "init_db", lambda: None)


class InMemoryStore:
    """A tiny dict-backed stand-in for the crud layer.

    Mirrors the real crud contract exactly: returns plain dicts (or None for a
    missing id), so the routes can't tell the difference.
    """

    def __init__(self):
        self.rows = {}
        self.next_id = 1

    def create(self, data: TaskCreate) -> dict:
        row = {
            "id": self.next_id,
            "raw_text": data.raw_text,
            "title": data.title,
            "category": data.category,
            "priority": data.priority,
            "due_date": data.due_date,
            "completed": False,
            "created_at": datetime(2026, 1, 1, 12, 0, 0),
        }
        self.rows[self.next_id] = row
        self.next_id += 1
        return dict(row)

    def list(self, category=None, completed=None) -> list:
        items = list(self.rows.values())
        if category is not None:
            items = [r for r in items if r["category"] == category]
        if completed is not None:
            items = [r for r in items if bool(r["completed"]) == completed]
        # newest first, mirroring the real ORDER BY created_at DESC, id DESC
        return [dict(r) for r in sorted(items, key=lambda r: r["id"], reverse=True)]

    def get(self, task_id: int):
        row = self.rows.get(task_id)
        return dict(row) if row else None

    def update(self, task_id: int, data: TaskUpdate):
        if task_id not in self.rows:
            return None
        self.rows[task_id].update(data.model_dump(exclude_unset=True))
        return dict(self.rows[task_id])

    def delete(self, task_id: int) -> bool:
        return self.rows.pop(task_id, None) is not None


@pytest.fixture
def store(monkeypatch):
    """Swap the DB-backed crud functions for the in-memory store."""
    s = InMemoryStore()
    monkeypatch.setattr(crud, "create_task", s.create)
    monkeypatch.setattr(crud, "list_tasks", lambda category=None, completed=None: s.list(category, completed))
    monkeypatch.setattr(crud, "get_task", s.get)
    monkeypatch.setattr(crud, "update_task", s.update)
    monkeypatch.setattr(crud, "delete_task", s.delete)
    return s


@pytest.fixture
def client(store):
    """A TestClient backed by the in-memory store (no MySQL required)."""
    with TestClient(app) as test_client:
        yield test_client
