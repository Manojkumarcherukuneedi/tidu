"""Shared pytest fixtures that keep the suite hermetic.

External dependencies are stubbed so the suite runs offline, free, and with no
setup:

  1. The LLM (`ai_service._call_llm`) is blocked by default (autouse), so no
     test reaches the real Anthropic API. Tests override it for specific output.
  2. The database (`crud.*`) is an in-memory store — users + per-user tasks.
  3. `database.init_db` is no-op'd, and `auth.JWT_SECRET` is set to a test value
     so JWTs can be signed/verified without a real secret.

Auth fixtures:
  - `client`     -> a TestClient authenticated as a default user (user A).
  - `anon_client`-> a TestClient with no Authorization header.
  - `make_user`  -> create another user and get a valid token (e.g. user B).
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend import ai_service, auth, crud, database
from backend.main import app
from backend.models import TaskCreate, TaskUpdate


def _blocked_llm(*_args, **_kwargs):
    raise RuntimeError("LLM call blocked in tests (no real API call allowed)")


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    """Applied to every test: no real LLM, no DB bootstrap, a test JWT secret.

    Both LLM entry points are blocked: `_call_llm` (enrichment) and `_complete`
    (the shared boundary used by subtask breakdown + plan-my-day). So no test
    can reach the real API regardless of which feature it exercises.
    """
    monkeypatch.setattr(ai_service, "_call_llm", _blocked_llm)
    monkeypatch.setattr(ai_service, "_complete", _blocked_llm)
    monkeypatch.setattr(database, "init_db", lambda: None)
    monkeypatch.setattr(auth, "JWT_SECRET", "test-secret-key-not-used-in-production")


class InMemoryStore:
    """Dict-backed stand-in for the crud layer — users and per-user tasks.

    Mirrors the real crud contract: returns plain dicts (or None), and every
    task method is scoped to a user_id, so the ownership rules are exercised.
    """

    def __init__(self):
        self.users = {}
        self.tasks = {}
        self.subtasks = {}
        self.next_user_id = 1
        self.next_task_id = 1
        self.next_subtask_id = 1

    # --- users ---
    def create_user(self, email, password_hash):
        row = {
            "id": self.next_user_id,
            "email": email,
            "password_hash": password_hash,
            "created_at": datetime(2026, 1, 1, 12, 0, 0),
        }
        self.users[self.next_user_id] = row
        self.next_user_id += 1
        return dict(row)

    def get_user_by_email(self, email):
        for u in self.users.values():
            if u["email"] == email:
                return dict(u)
        return None

    def get_user_by_id(self, user_id):
        u = self.users.get(user_id)
        return dict(u) if u else None

    # --- tasks (scoped to user_id) ---
    def create_task(self, data: TaskCreate, user_id: int):
        row = {
            "id": self.next_task_id,
            "user_id": user_id,
            "raw_text": data.raw_text,
            "title": data.title,
            "category": data.category,
            "priority": data.priority,
            "due_date": data.due_date,
            "completed": False,
            "created_at": datetime(2026, 1, 1, 12, 0, 0),
        }
        self.tasks[self.next_task_id] = row
        self.next_task_id += 1
        return dict(row)

    def list_tasks(self, user_id, category=None, completed=None):
        items = [t for t in self.tasks.values() if t["user_id"] == user_id]
        if category is not None:
            items = [t for t in items if t["category"] == category]
        if completed is not None:
            items = [t for t in items if bool(t["completed"]) == completed]
        out = []
        for t in sorted(items, key=lambda t: t["id"], reverse=True):
            d = dict(t)
            d["subtasks"] = self.get_subtasks_for_task(t["id"])
            out.append(d)
        return out

    def get_task(self, task_id, user_id):
        t = self.tasks.get(task_id)
        if not t or t["user_id"] != user_id:
            return None
        d = dict(t)
        d["subtasks"] = self.get_subtasks_for_task(task_id)
        return d

    def update_task(self, task_id, user_id, data: TaskUpdate):
        t = self.tasks.get(task_id)
        if not t or t["user_id"] != user_id:
            return None
        t.update(data.model_dump(exclude_unset=True))
        return dict(t)

    def delete_task(self, task_id, user_id):
        t = self.tasks.get(task_id)
        if not t or t["user_id"] != user_id:
            return False
        del self.tasks[task_id]
        return True

    # --- subtasks (Slice 7) ---
    def _owns_task(self, task_id, user_id):
        t = self.tasks.get(task_id)
        return bool(t) and t["user_id"] == user_id

    def get_subtasks_for_task(self, task_id):
        return [dict(s) for s in self.subtasks.values() if s["task_id"] == task_id]

    def get_subtasks_for_tasks(self, task_ids):
        grouped = {}
        for s in self.subtasks.values():
            if s["task_id"] in task_ids:
                grouped.setdefault(s["task_id"], []).append(dict(s))
        return grouped

    def replace_subtasks(self, task_id, texts):
        self.subtasks = {
            sid: s for sid, s in self.subtasks.items() if s["task_id"] != task_id
        }
        for text in texts:
            self.subtasks[self.next_subtask_id] = {
                "id": self.next_subtask_id,
                "task_id": task_id,
                "text": text,
                "completed": False,
                "created_at": datetime(2026, 1, 1, 12, 0, 0),
            }
            self.next_subtask_id += 1
        return self.get_subtasks_for_task(task_id)

    def add_subtask(self, task_id, text):
        row = {
            "id": self.next_subtask_id,
            "task_id": task_id,
            "text": text,
            "completed": False,
            "created_at": datetime(2026, 1, 1, 12, 0, 0),
        }
        self.subtasks[self.next_subtask_id] = row
        self.next_subtask_id += 1
        return dict(row)

    def get_subtask(self, subtask_id, user_id):
        s = self.subtasks.get(subtask_id)
        if not s or not self._owns_task(s["task_id"], user_id):
            return None
        return dict(s)

    def update_subtask(self, subtask_id, user_id, data):
        s = self.subtasks.get(subtask_id)
        if not s or not self._owns_task(s["task_id"], user_id):
            return None
        s.update(data.model_dump(exclude_unset=True))
        return dict(s)

    def delete_subtask(self, subtask_id, user_id):
        s = self.subtasks.get(subtask_id)
        if not s or not self._owns_task(s["task_id"], user_id):
            return False
        del self.subtasks[subtask_id]
        return True


@pytest.fixture
def store(monkeypatch, _hermetic):
    s = InMemoryStore()
    monkeypatch.setattr(crud, "create_user", s.create_user)
    monkeypatch.setattr(crud, "get_user_by_email", s.get_user_by_email)
    monkeypatch.setattr(crud, "get_user_by_id", s.get_user_by_id)
    monkeypatch.setattr(crud, "create_task", s.create_task)
    monkeypatch.setattr(crud, "list_tasks", s.list_tasks)
    monkeypatch.setattr(crud, "get_task", s.get_task)
    monkeypatch.setattr(crud, "update_task", s.update_task)
    monkeypatch.setattr(crud, "delete_task", s.delete_task)
    # subtasks (Slice 7)
    monkeypatch.setattr(crud, "get_subtasks_for_task", s.get_subtasks_for_task)
    monkeypatch.setattr(crud, "get_subtasks_for_tasks", s.get_subtasks_for_tasks)
    monkeypatch.setattr(crud, "replace_subtasks", s.replace_subtasks)
    monkeypatch.setattr(crud, "add_subtask", s.add_subtask)
    monkeypatch.setattr(crud, "get_subtask", s.get_subtask)
    monkeypatch.setattr(crud, "update_subtask", s.update_subtask)
    monkeypatch.setattr(crud, "delete_subtask", s.delete_subtask)
    return s


@pytest.fixture
def make_user(store):
    """Create a user directly in the store and return (user, bearer_token).

    Uses a placeholder hash — these users authenticate via their token, so no
    bcrypt is needed here (the real signup/login path is exercised separately).
    """
    def _make(email):
        user = store.create_user(email, "placeholder-hash")
        token = auth.create_access_token(user["id"])
        return user, token

    return _make


@pytest.fixture
def client(store, make_user):
    """TestClient authenticated as a default user (user A)."""
    _, token = make_user("user-a@example.com")
    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c


@pytest.fixture
def anon_client(store):
    """TestClient with no auth header (for auth/unauthorized tests)."""
    with TestClient(app) as c:
        yield c
