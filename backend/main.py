"""FastAPI application entry point for Tidu.

Slice 1: app wiring, MySQL table bootstrap, health check.
Slice 2: CRUD routes for /tasks.
Slice 3: AI enrichment on POST /tasks.
Slice 6: email/password auth (JWT). All /tasks routes now require a logged-in
         user and are scoped to that user.

Route handlers here are intentionally thin: they validate input via Pydantic,
delegate database work to `crud`, LLM work to `ai_service`, and auth to `auth`.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

from . import ai_service, auth, crud, database
from .models import (
    BreakdownResponse,
    DayPlan,
    HealthResponse,
    LoginRequest,
    SignupRequest,
    Subtask,
    SubtaskCreate,
    SubtaskUpdate,
    Task,
    TaskCreate,
    TaskUpdate,
    Token,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_task_organizer")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Bootstrap the database on startup without crashing if MySQL is down."""
    try:
        database.init_db()
        logger.info("Database initialized: `users` and `tasks` tables are ready.")
    except Exception as exc:  # noqa: BLE001 - log and continue
        logger.warning(
            "Could not initialize database on startup (%s). "
            "The app will still start; /health will report the DB status.",
            exc,
        )
    yield


app = FastAPI(title="Tidu", version="0.6.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Shared dependency: fetch the current user's task or 404 ------------------
# Depends on get_current_user, so the lookup is automatically scoped to the
# logged-in user. A task that exists but belongs to someone else returns the
# same 404 as one that doesn't exist — no existence leak (see crud.get_task).
def get_existing_task(
    task_id: int,
    current_user: dict = Depends(auth.get_current_user),
) -> dict:
    task = crud.get_task(task_id, current_user["id"])
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    return task


# --- System -------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Liveness + DB connectivity check (unauthenticated)."""
    db_ok = database.check_connection()
    return HealthResponse(status="ok", database="connected" if db_ok else "disconnected")


# --- Auth ---------------------------------------------------------------------
@app.post("/auth/signup", response_model=Token, status_code=status.HTTP_201_CREATED, tags=["auth"])
def signup(payload: SignupRequest) -> Token:
    """Create a user and return a JWT. 409 if the email is already registered."""
    if crud.get_user_by_email(payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    user = crud.create_user(payload.email, auth.hash_password(payload.password))
    token = auth.create_access_token(user["id"])
    return Token(access_token=token, email=user["email"])


@app.post("/auth/login", response_model=Token, tags=["auth"])
def login(payload: LoginRequest) -> Token:
    """Verify credentials and return a JWT. 401 on any mismatch.

    The same 401 is returned for an unknown email and a wrong password, so we
    don't reveal which emails are registered.
    """
    user = crud.get_user_by_email(payload.email)
    if user is None or not auth.verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = auth.create_access_token(user["id"])
    return Token(access_token=token, email=user["email"])


# --- Tasks (all require auth, all scoped to the current user) ------------------
@app.post("/tasks", response_model=Task, status_code=status.HTTP_201_CREATED, tags=["tasks"])
def create_task(
    payload: TaskCreate,
    current_user: dict = Depends(auth.get_current_user),
) -> dict:
    """Create a task for the current user, enriching blank fields via the LLM."""
    if ai_service.needs_enrichment(payload):
        enrichment = ai_service.enrich_task(payload.raw_text)
        payload = ai_service.apply_enrichment(payload, enrichment)
    return crud.create_task(payload, current_user["id"])


@app.get("/tasks", response_model=list[Task], tags=["tasks"])
def list_tasks(
    category: str | None = None,
    completed: bool | None = None,
    current_user: dict = Depends(auth.get_current_user),
) -> list[dict]:
    """List ONLY the current user's tasks, optionally filtered."""
    return crud.list_tasks(current_user["id"], category=category, completed=completed)


@app.get("/tasks/{task_id}", response_model=Task, tags=["tasks"])
def get_task(task: dict = Depends(get_existing_task)) -> dict:
    """Return one of the current user's tasks, or 404."""
    return task


@app.put("/tasks/{task_id}", response_model=Task, tags=["tasks"])
def update_task(
    task_id: int,
    payload: TaskUpdate,
    current_user: dict = Depends(auth.get_current_user),
    _existing: dict = Depends(get_existing_task),
) -> dict:
    """Partially update the current user's task. 404 if missing or not theirs."""
    updated = crud.update_task(task_id, current_user["id"], payload)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    return updated


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["tasks"])
def delete_task(
    task_id: int,
    current_user: dict = Depends(auth.get_current_user),
    _existing: dict = Depends(get_existing_task),
) -> Response:
    """Delete the current user's task. 204 on success, 404 if missing/not theirs."""
    crud.delete_task(task_id, current_user["id"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Slice 7: AI subtask breakdown --------------------------------------------
@app.post("/tasks/{task_id}/breakdown", response_model=BreakdownResponse, tags=["subtasks"])
def breakdown_task(task: dict = Depends(get_existing_task)) -> BreakdownResponse:
    """Ask the LLM to break the (owned) task into subtasks and save them.

    Never 500s: if the AI can't produce steps, `generated` is False and the
    existing subtasks (if any) are left untouched.
    """
    texts = ai_service.generate_subtasks(task.get("title") or task.get("raw_text") or "")
    if not texts:
        return BreakdownResponse(subtasks=task.get("subtasks", []), generated=False)
    saved = crud.replace_subtasks(task["id"], texts)
    return BreakdownResponse(subtasks=saved, generated=True)


@app.post(
    "/tasks/{task_id}/subtasks",
    response_model=Subtask,
    status_code=status.HTTP_201_CREATED,
    tags=["subtasks"],
)
def add_subtask(payload: SubtaskCreate, task: dict = Depends(get_existing_task)) -> dict:
    """Manually add a subtask to a task the current user owns (404 otherwise)."""
    return crud.add_subtask(task["id"], payload.text.strip())


@app.put("/subtasks/{subtask_id}", response_model=Subtask, tags=["subtasks"])
def update_subtask(
    subtask_id: int,
    payload: SubtaskUpdate,
    current_user: dict = Depends(auth.get_current_user),
) -> dict:
    """Edit a subtask (toggle complete and/or change text). 404 if not the owner's."""
    updated = crud.update_subtask(subtask_id, current_user["id"], payload)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Subtask {subtask_id} not found")
    return updated


@app.delete("/subtasks/{subtask_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["subtasks"])
def delete_subtask(
    subtask_id: int,
    current_user: dict = Depends(auth.get_current_user),
) -> Response:
    """Delete a subtask the user owns. 204 on success, 404 otherwise."""
    if not crud.delete_subtask(subtask_id, current_user["id"]):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Subtask {subtask_id} not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Slice 7: Plan my day -----------------------------------------------------
@app.post("/plan-my-day", response_model=DayPlan, tags=["tasks"])
def plan_my_day(current_user: dict = Depends(auth.get_current_user)) -> DayPlan:
    """Return a prioritized plan over the user's incomplete tasks.

    Degrades to a basic due-date/priority sort (source="fallback") if the AI
    is unavailable — never 500s.
    """
    tasks = crud.list_tasks(current_user["id"], completed=False)
    return ai_service.plan_day(tasks)
