"""Pydantic schemas for the AI Task Organizer.

Three kinds of schema, deliberately separated:
  - TaskCreate  -> what a client may send to POST /tasks
  - TaskUpdate  -> what a client may send to PUT /tasks/{id} (all optional)
  - Task        -> what we send back (the full persisted row)

Keeping input and output schemas distinct is a core API-design idea: the
fields a client is *allowed to set* are not the same as the fields we *store
and return*. A client must never be able to set `id` or `created_at` (the DB
owns those), and the response should never be missing them.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

# Fallback values when the LLM call fails or returns invalid JSON (slice 3).
DEFAULT_CATEGORY = "Uncategorized"
DEFAULT_PRIORITY = "Medium"

# A closed set of allowed priorities. Using Literal means Pydantic rejects
# anything else with a 422 automatically — no hand-written validation needed.
Priority = Literal["High", "Medium", "Low"]


class HealthResponse(BaseModel):
    """Payload returned by GET /health."""

    status: str
    database: str


class TaskCreate(BaseModel):
    """Request body for POST /tasks.

    `raw_text` is the only required field (the natural-language input). The
    rest are optional and set manually for now; in slice 3 the LLM will fill
    category / priority / due_date when they're omitted.

    extra="forbid" makes Pydantic reject unknown fields with a 422 instead of
    silently dropping them — so a typo like {"priorty": "High"} is an error,
    not a silently-ignored no-op.
    """

    model_config = ConfigDict(extra="forbid")

    raw_text: str
    title: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[Priority] = None
    due_date: Optional[date] = None


class TaskUpdate(BaseModel):
    """Request body for PUT /tasks/{id}.

    Every field is optional so the client can send a *partial* update — only
    the fields present in the JSON get changed. We distinguish "field absent"
    from "field set to null" using Pydantic's `exclude_unset` at the call site
    (see crud.update_task).

    Note `raw_text` is intentionally not updatable here: the brief's allowed
    update fields are title / category / priority / due_date / completed.
    """

    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[Priority] = None
    due_date: Optional[date] = None
    completed: Optional[bool] = None


class Task(BaseModel):
    """Response model: a full task row as stored in MySQL."""

    # from_attributes isn't needed (we return dicts), but allows ORM-style use.
    model_config = ConfigDict(from_attributes=True)

    id: int
    raw_text: Optional[str] = None
    title: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[date] = None
    completed: bool = False
    created_at: Optional[datetime] = None
