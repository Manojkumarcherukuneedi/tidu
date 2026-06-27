"""FastAPI application entry point for the AI Task Organizer.

Slice 1: app wiring, MySQL table bootstrap, health check.
Slice 2: CRUD routes for /tasks (no AI yet).
Slice 3: AI enrichment on POST /tasks (read/update/delete stay AI-free).

Route handlers here are intentionally thin: they validate input via Pydantic,
delegate all database work to `crud` and all LLM work to `ai_service`, and
translate "not found" into a 404.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

from . import ai_service, crud, database
from .models import HealthResponse, Task, TaskCreate, TaskUpdate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_task_organizer")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Bootstrap the database on startup without crashing if MySQL is down."""
    try:
        database.init_db()
        logger.info("Database initialized: `tasks` table is ready.")
    except Exception as exc:  # noqa: BLE001 - log and continue
        logger.warning(
            "Could not initialize database on startup (%s). "
            "The app will still start; /health will report the DB status.",
            exc,
        )
    yield


app = FastAPI(title="AI Task Organizer", version="0.3.0", lifespan=lifespan)

# Allow the React dev server (slice 4) to call the API during development.
# Both localhost and 127.0.0.1 are listed because the browser treats them as
# distinct origins, and Vite/users may use either.
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


# --- Shared dependency: fetch a task or raise 404 -----------------------------
# Centralizing this here means GET-one, PUT, and DELETE all share the exact
# same "does this id exist?" check and the exact same 404 error shape. No
# duplicated lookup logic, and one place to change the error message.
def get_existing_task(task_id: int) -> dict:
    task = crud.get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    return task


# --- System -------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Liveness + DB connectivity check."""
    db_ok = database.check_connection()
    return HealthResponse(
        status="ok",
        database="connected" if db_ok else "disconnected",
    )


# --- Tasks CRUD ---------------------------------------------------------------
@app.post(
    "/tasks",
    response_model=Task,
    status_code=status.HTTP_201_CREATED,
    tags=["tasks"],
)
def create_task(payload: TaskCreate) -> dict:
    """Create a task, enriching blank fields via the LLM.

    The AI step never blocks creation: `ai_service.enrich_task` degrades to safe
    defaults on any failure, so this route always returns 201. We only call the
    LLM when the user left a field for it to fill (user-provided values win).
    """
    if ai_service.needs_enrichment(payload):
        enrichment = ai_service.enrich_task(payload.raw_text)
        payload = ai_service.apply_enrichment(payload, enrichment)
    return crud.create_task(payload)


@app.get("/tasks", response_model=list[Task], tags=["tasks"])
def list_tasks(
    category: str | None = None,
    completed: bool | None = None,
) -> list[dict]:
    """List tasks, optionally filtered by ?category= and ?completed=.

    Returns an empty array (200) when nothing matches — not an error.
    """
    return crud.list_tasks(category=category, completed=completed)


@app.get("/tasks/{task_id}", response_model=Task, tags=["tasks"])
def get_task(task: dict = Depends(get_existing_task)) -> dict:
    """Return one task, or 404 if the id doesn't exist."""
    return task


@app.put("/tasks/{task_id}", response_model=Task, tags=["tasks"])
def update_task(
    task_id: int,
    payload: TaskUpdate,
    _existing: dict = Depends(get_existing_task),
) -> dict:
    """Partially update a task. 404 if it doesn't exist (via the dependency)."""
    updated = crud.update_task(task_id, payload)
    # The dependency already guaranteed existence, so this is defensive.
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    return updated


@app.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["tasks"],
)
def delete_task(
    task_id: int,
    _existing: dict = Depends(get_existing_task),
) -> Response:
    """Delete a task. 204 on success, 404 if it doesn't exist."""
    crud.delete_task(task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
