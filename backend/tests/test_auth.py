"""Auth tests: signup, login, that /tasks requires auth, and per-user scoping.

Hermetic — the in-memory store stands in for the DB, and real bcrypt + JWT run
(no network, no API key). Signup/login exercise the genuine hashing path.
"""


# --- Signup -------------------------------------------------------------------
def test_signup_returns_token_and_no_hash(anon_client):
    resp = anon_client.post(
        "/auth/signup", json={"email": "new@example.com", "password": "password123"}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["email"] == "new@example.com"
    # The hash must never appear in a response.
    assert "password" not in body
    assert "password_hash" not in body


def test_signup_duplicate_email_409(anon_client):
    anon_client.post("/auth/signup", json={"email": "dup@example.com", "password": "password123"})
    resp = anon_client.post("/auth/signup", json={"email": "dup@example.com", "password": "password123"})
    assert resp.status_code == 409
    assert "already registered" in resp.json()["detail"].lower()


def test_signup_short_password_422(anon_client):
    resp = anon_client.post("/auth/signup", json={"email": "x@example.com", "password": "short"})
    assert resp.status_code == 422


def test_signup_invalid_email_422(anon_client):
    resp = anon_client.post("/auth/signup", json={"email": "not-an-email", "password": "password123"})
    assert resp.status_code == 422


# --- Login --------------------------------------------------------------------
def test_login_success(anon_client):
    anon_client.post("/auth/signup", json={"email": "log@example.com", "password": "password123"})
    resp = anon_client.post("/auth/login", json={"email": "log@example.com", "password": "password123"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]


def test_login_wrong_password_401(anon_client):
    anon_client.post("/auth/signup", json={"email": "wp@example.com", "password": "password123"})
    resp = anon_client.post("/auth/login", json={"email": "wp@example.com", "password": "wrongpassword"})
    assert resp.status_code == 401


def test_login_unknown_email_401(anon_client):
    resp = anon_client.post("/auth/login", json={"email": "ghost@example.com", "password": "password123"})
    assert resp.status_code == 401


# --- Protection ---------------------------------------------------------------
def test_tasks_require_auth(anon_client):
    assert anon_client.get("/tasks").status_code == 401
    assert anon_client.post("/tasks", json={"raw_text": "x"}).status_code == 401
    assert anon_client.get("/tasks/1").status_code == 401


def test_invalid_token_rejected(anon_client):
    resp = anon_client.get("/tasks", headers={"Authorization": "Bearer not.a.real.token"})
    assert resp.status_code == 401


def test_token_from_signup_works(anon_client):
    token = anon_client.post(
        "/auth/signup", json={"email": "flow@example.com", "password": "password123"}
    ).json()["access_token"]
    resp = anon_client.get("/tasks", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []  # brand-new account starts empty


# --- Per-user scoping ---------------------------------------------------------
def test_cannot_access_another_users_task(client, anon_client, make_user):
    # user A (the authenticated `client`) creates a task
    created = client.post(
        "/tasks",
        json={"raw_text": "A's secret", "category": "Private", "priority": "High", "due_date": "2026-01-01"},
    ).json()
    task_id = created["id"]

    # user B gets a token
    _, token_b = make_user("user-b@example.com")
    auth_b = {"Authorization": f"Bearer {token_b}"}

    # B must NOT be able to read / update / delete A's task — 404, not 403,
    # so we don't leak that the id exists.
    assert anon_client.get(f"/tasks/{task_id}", headers=auth_b).status_code == 404
    assert anon_client.put(f"/tasks/{task_id}", json={"completed": True}, headers=auth_b).status_code == 404
    assert anon_client.delete(f"/tasks/{task_id}", headers=auth_b).status_code == 404

    # B's own board is empty; A still sees the task.
    assert anon_client.get("/tasks", headers=auth_b).json() == []
    assert client.get(f"/tasks/{task_id}").status_code == 200
