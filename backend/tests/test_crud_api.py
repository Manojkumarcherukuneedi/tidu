"""CRUD + validation tests for the /tasks routes.

Runs against the in-memory store (conftest `client` fixture), so no MySQL is
required. Tasks are created with explicit category/priority/due_date so the
enrichment step is skipped (needs_enrichment == False) and the cases are fully
deterministic.
"""

FULL_TASK = {
    "raw_text": "finish DB assignment",
    "title": "DB assignment",
    "category": "School",
    "priority": "High",
    "due_date": "2026-07-03",
}


# --- Create -------------------------------------------------------------------


def test_create_returns_201_with_full_row(client):
    resp = client.post("/tasks", json=FULL_TASK)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["id"]
    assert body["created_at"]
    assert body["completed"] is False
    assert body["category"] == "School"
    assert body["priority"] == "High"
    assert body["due_date"] == "2026-07-03"


def test_create_requires_raw_text(client):
    resp = client.post("/tasks", json={"title": "no raw text"})
    assert resp.status_code == 422


# --- Read (list + one) --------------------------------------------------------


def test_list_empty_returns_empty_array(client):
    resp = client.get("/tasks")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_returns_all(client):
    client.post("/tasks", json=FULL_TASK)
    client.post("/tasks", json={**FULL_TASK, "category": "Work"})
    resp = client.get("/tasks")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_filter_by_category(client):
    client.post("/tasks", json={**FULL_TASK, "category": "School"})
    client.post("/tasks", json={**FULL_TASK, "category": "Work"})
    resp = client.get("/tasks?category=Work")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["category"] == "Work"


def test_list_filter_by_completed_returns_empty_when_none_match(client):
    client.post("/tasks", json=FULL_TASK)
    resp = client.get("/tasks?completed=true")
    assert resp.status_code == 200
    assert resp.json() == []  # empty array, not an error


def test_get_one_returns_task(client):
    created = client.post("/tasks", json=FULL_TASK).json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["raw_text"] == "finish DB assignment"


def test_get_one_unknown_id_returns_404(client):
    resp = client.get("/tasks/999999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Task 999999 not found"


# --- Update (partial) ---------------------------------------------------------


def test_partial_update_changes_only_sent_fields(client):
    created = client.post("/tasks", json=FULL_TASK).json()
    resp = client.put(f"/tasks/{created['id']}", json={"completed": True, "priority": "Low"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["completed"] is True
    assert body["priority"] == "Low"
    assert body["title"] == "DB assignment"  # untouched
    assert body["category"] == "School"      # untouched


def test_update_unknown_id_returns_404(client):
    resp = client.put("/tasks/999999", json={"completed": True})
    assert resp.status_code == 404


# --- Delete -------------------------------------------------------------------


def test_delete_returns_204_and_task_is_gone(client):
    created = client.post("/tasks", json=FULL_TASK).json()
    resp = client.delete(f"/tasks/{created['id']}")
    assert resp.status_code == 204
    assert client.get(f"/tasks/{created['id']}").status_code == 404


def test_delete_unknown_id_returns_404(client):
    resp = client.delete("/tasks/999999")
    assert resp.status_code == 404


# --- Validation ---------------------------------------------------------------


def test_create_rejects_invalid_priority(client):
    resp = client.post("/tasks", json={"raw_text": "x", "priority": "Urgent"})
    assert resp.status_code == 422


def test_create_rejects_unknown_field(client):
    resp = client.post("/tasks", json={"raw_text": "x", "priorty": "High"})
    assert resp.status_code == 422


def test_update_rejects_invalid_priority(client):
    created = client.post("/tasks", json=FULL_TASK).json()
    resp = client.put(f"/tasks/{created['id']}", json={"priority": "Critical"})
    assert resp.status_code == 422


def test_update_rejects_unknown_field(client):
    created = client.post("/tasks", json=FULL_TASK).json()
    resp = client.put(f"/tasks/{created['id']}", json={"completd": True})
    assert resp.status_code == 422
