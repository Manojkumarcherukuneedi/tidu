"""Data-access layer for tasks (the "repository" / "service" layer).

Every SQL statement in the app lives here so route handlers stay thin and the
database details are in one place. Two rules this module enforces:

  1. Parameterized queries only. We pass user values as parameters (the `%s`
     placeholders + a params tuple), never by formatting them into the SQL
     string. PyMySQL escapes them for us, which is what prevents SQL injection.
     Column/table *names* — which are never user input — are the only things
     we ever interpolate into SQL text.

  2. These functions return plain dicts (or None), and know nothing about HTTP.
     Turning "not found" into a 404 is the route layer's job, not theirs.
"""

from __future__ import annotations

from typing import Optional

from .database import connection
from .models import TaskCreate, TaskUpdate

# Columns we read back for every task. Listed explicitly (rather than SELECT *)
# so the response shape is stable even if the table later gains columns.
_TASK_COLUMNS = (
    "id, raw_text, title, category, priority, due_date, completed, created_at"
)


def create_task(data: TaskCreate) -> dict:
    """Insert a new task and return the full persisted row (incl. id, created_at)."""
    sql = (
        "INSERT INTO tasks (raw_text, title, category, priority, due_date) "
        "VALUES (%s, %s, %s, %s, %s)"
    )
    params = (data.raw_text, data.title, data.category, data.priority, data.due_date)
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            new_id = cur.lastrowid
    # Re-fetch so the client gets DB-populated defaults (completed, created_at).
    task = get_task(new_id)
    assert task is not None  # we just inserted it
    return task


def list_tasks(
    category: Optional[str] = None,
    completed: Optional[bool] = None,
) -> list[dict]:
    """Return tasks, optionally filtered by category and/or completed.

    Filters are built dynamically but *values stay parameterized* — we only
    ever append fixed "col = %s" fragments and push the value into params.
    """
    sql = f"SELECT {_TASK_COLUMNS} FROM tasks"
    clauses: list[str] = []
    params: list = []

    if category is not None:
        clauses.append("category = %s")
        params.append(category)
    if completed is not None:
        clauses.append("completed = %s")
        params.append(completed)

    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC, id DESC"

    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())


def get_task(task_id: int) -> Optional[dict]:
    """Return one task by id, or None if it doesn't exist."""
    sql = f"SELECT {_TASK_COLUMNS} FROM tasks WHERE id = %s"
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (task_id,))
            return cur.fetchone()


def update_task(task_id: int, data: TaskUpdate) -> Optional[dict]:
    """Apply a partial update and return the updated row (or None if missing).

    `exclude_unset=True` gives us only the fields the client actually sent, so
    omitted fields are left untouched. If nothing was sent, we no-op and just
    return the current row.
    """
    fields = data.model_dump(exclude_unset=True)
    if not fields:
        return get_task(task_id)

    # Build "col = %s, col = %s" from the *known* field names (not user input),
    # and pass the values as parameters.
    set_clause = ", ".join(f"{col} = %s" for col in fields)
    params = list(fields.values()) + [task_id]
    sql = f"UPDATE tasks SET {set_clause} WHERE id = %s"

    with connection() as conn:
        with conn.cursor() as cur:
            affected = cur.execute(sql, params)
    if affected == 0 and get_task(task_id) is None:
        return None
    return get_task(task_id)


def delete_task(task_id: int) -> bool:
    """Delete a task. Returns True if a row was deleted, False if none existed."""
    sql = "DELETE FROM tasks WHERE id = %s"
    with connection() as conn:
        with conn.cursor() as cur:
            affected = cur.execute(sql, (task_id,))
    return affected > 0
