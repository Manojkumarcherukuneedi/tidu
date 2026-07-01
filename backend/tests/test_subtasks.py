"""Tests for AI subtask breakdown (Slice 7).

Hermetic: the LLM boundary (`ai_service._complete`) is mocked per-test, the DB
is the in-memory store. Covers a valid breakdown, graceful fallback on a bad AI
response (no 500), per-user scoping (404), and subtask toggle/delete.
"""

from backend import ai_service

FULL = {"raw_text": "plan birthday party", "title": "plan birthday party",
        "category": "Personal", "priority": "Medium", "due_date": "2026-07-01"}


def test_breakdown_generates_and_saves(client, monkeypatch):
    monkeypatch.setattr(
        ai_service, "_complete",
        lambda *a, **k: '{"subtasks": ["Pick a venue", "Send invites", "Order cake"]}',
    )
    task = client.post("/tasks", json=FULL).json()
    resp = client.post(f"/tasks/{task['id']}/breakdown")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["generated"] is True
    assert [s["text"] for s in body["subtasks"]] == ["Pick a venue", "Send invites", "Order cake"]
    # subtasks come back when fetching the task too
    assert len(client.get(f"/tasks/{task['id']}").json()["subtasks"]) == 3


def test_breakdown_bad_ai_falls_back_no_500(client, monkeypatch):
    monkeypatch.setattr(ai_service, "_complete", lambda *a, **k: "sorry, I cannot help")
    task = client.post("/tasks", json=FULL).json()
    resp = client.post(f"/tasks/{task['id']}/breakdown")
    assert resp.status_code == 200  # NOT a 500
    body = resp.json()
    assert body["generated"] is False
    assert body["subtasks"] == []


def test_breakdown_requires_auth(anon_client):
    assert anon_client.post("/tasks/1/breakdown").status_code == 401


def test_breakdown_other_users_task_404(client, anon_client, make_user, monkeypatch):
    monkeypatch.setattr(ai_service, "_complete", lambda *a, **k: '{"subtasks": ["a", "b", "c"]}')
    task = client.post("/tasks", json=FULL).json()
    _, token_b = make_user("b-breakdown@example.com")
    resp = anon_client.post(
        f"/tasks/{task['id']}/breakdown", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 404


def test_subtask_toggle_delete_and_scope(client, anon_client, make_user, monkeypatch):
    monkeypatch.setattr(ai_service, "_complete", lambda *a, **k: '{"subtasks": ["one", "two"]}')
    task = client.post("/tasks", json=FULL).json()
    subs = client.post(f"/tasks/{task['id']}/breakdown").json()["subtasks"]
    sid = subs[0]["id"]

    # owner toggles complete
    r = client.put(f"/subtasks/{sid}", json={"completed": True})
    assert r.status_code == 200 and r.json()["completed"] is True

    # another user can neither toggle nor delete it (404, not 403)
    _, token_b = make_user("b-subtask@example.com")
    auth_b = {"Authorization": f"Bearer {token_b}"}
    assert anon_client.put(f"/subtasks/{sid}", json={"completed": False}, headers=auth_b).status_code == 404
    assert anon_client.delete(f"/subtasks/{sid}", headers=auth_b).status_code == 404

    # owner deletes -> 204, and it's gone
    assert client.delete(f"/subtasks/{sid}").status_code == 204
    assert len(client.get(f"/tasks/{task['id']}").json()["subtasks"]) == 1


def test_subtask_edit_text(client, monkeypatch):
    monkeypatch.setattr(ai_service, "_complete", lambda *a, **k: '{"subtasks": ["Original step"]}')
    task = client.post("/tasks", json=FULL).json()
    sid = client.post(f"/tasks/{task['id']}/breakdown").json()["subtasks"][0]["id"]
    # partial update: change only the text, completed untouched
    r = client.put(f"/subtasks/{sid}", json={"text": "Edited step text"})
    assert r.status_code == 200
    assert r.json()["text"] == "Edited step text"
    assert r.json()["completed"] is False


def test_subtask_add_manual(client):
    task = client.post("/tasks", json=FULL).json()
    r = client.post(f"/tasks/{task['id']}/subtasks", json={"text": "A manual step"})
    assert r.status_code == 201, r.text
    assert r.json()["text"] == "A manual step"
    assert r.json()["completed"] is False
    # it shows up on the task
    assert "A manual step" in [s["text"] for s in client.get(f"/tasks/{task['id']}").json()["subtasks"]]


def test_subtask_add_empty_rejected(client):
    task = client.post("/tasks", json=FULL).json()
    assert client.post(f"/tasks/{task['id']}/subtasks", json={"text": ""}).status_code == 422


def test_subtask_add_to_other_users_task_404(client, anon_client, make_user):
    task = client.post("/tasks", json=FULL).json()
    _, token_b = make_user("b-add@example.com")
    r = anon_client.post(
        f"/tasks/{task['id']}/subtasks",
        json={"text": "sneaky"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r.status_code == 404


def test_subtask_routes_require_auth(anon_client):
    assert anon_client.put("/subtasks/1", json={"completed": True}).status_code == 401
    assert anon_client.delete("/subtasks/1").status_code == 401
    assert anon_client.post("/tasks/1/subtasks", json={"text": "x"}).status_code == 401
