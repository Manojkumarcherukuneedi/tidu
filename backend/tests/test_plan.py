"""Tests for Plan my day (Slice 7).

Hermetic: `ai_service._complete` mocked per-test. Covers a valid AI plan,
graceful fallback to the basic sort when the AI fails, the empty case, that
completed tasks are excluded, and that the route requires auth.
"""

from backend import ai_service


def _task(client, title, priority, due):
    return client.post(
        "/tasks",
        json={"raw_text": title, "title": title, "category": "Work", "priority": priority, "due_date": due},
    ).json()


def test_plan_returns_ai_plan(client, monkeypatch):
    t1 = _task(client, "Report", "High", "2026-07-03")
    t2 = _task(client, "Dishes", "Low", "2026-07-10")
    plan_json = (
        '{"summary": "Do the report first.", "items": ['
        f'{{"task_id": {t1["id"]}, "reason": "High priority, due soon"}},'
        f'{{"task_id": {t2["id"]}, "reason": "Quick win"}}]}}'
    )
    monkeypatch.setattr(ai_service, "_complete", lambda *a, **k: plan_json)

    resp = client.post("/plan-my-day")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "ai"
    assert body["summary"] == "Do the report first."
    assert [i["task_id"] for i in body["items"]] == [t1["id"], t2["id"]]
    assert all(i["title"] for i in body["items"])  # titles resolved from real tasks


def test_plan_falls_back_on_ai_failure(client, monkeypatch):
    _task(client, "Report", "High", "2026-07-03")
    monkeypatch.setattr(ai_service, "_complete", lambda *a, **k: "this is not json")
    resp = client.post("/plan-my-day")
    assert resp.status_code == 200  # NOT a 500
    body = resp.json()
    assert body["source"] == "fallback"
    assert len(body["items"]) >= 1


def test_plan_ignores_ai_invented_task_ids(client, monkeypatch):
    # If the model references task_ids that don't belong to the user, they're
    # dropped; with none left it falls back to the basic sort.
    t1 = _task(client, "Real task", "Medium", "2026-07-05")
    monkeypatch.setattr(
        ai_service, "_complete",
        lambda *a, **k: '{"summary":"x","items":[{"task_id":99999,"reason":"nope"}]}',
    )
    body = client.post("/plan-my-day").json()
    assert body["source"] == "fallback"
    assert any(i["task_id"] == t1["id"] for i in body["items"])


def test_plan_empty_when_no_tasks(client):
    body = client.post("/plan-my-day").json()
    assert body["items"] == []


def test_plan_excludes_completed_tasks(client, monkeypatch):
    t = _task(client, "Done thing", "Low", "2026-07-01")
    client.put(f"/tasks/{t['id']}", json={"completed": True})
    monkeypatch.setattr(ai_service, "_complete", lambda *a, **k: "irrelevant")
    body = client.post("/plan-my-day").json()
    assert body["items"] == []  # only a completed task exists -> nothing to plan


def test_plan_requires_auth(anon_client):
    assert anon_client.post("/plan-my-day").status_code == 401
