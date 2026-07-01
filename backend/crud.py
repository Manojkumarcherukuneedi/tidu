"""Data-access layer (the "repository" / "service" layer).

Every SQL statement in the app lives here so route handlers stay thin and the
database details are in one place. Rules this module enforces:

  1. Parameterized queries only. User values go in as `%s` placeholders + a
     params tuple, never formatted into the SQL string. PyMySQL escapes them,
     which is what prevents SQL injection. Only column/table *names* (never user
     input) are interpolated into SQL text.

  2. These functions return plain dicts (or None), and know nothing about HTTP.

  3. Every task query is scoped to a `user_id` (Slice 6). A user can only ever
     touch their own rows — the ownership check is in the WHERE clause, so a
     task that exists but belongs to someone else simply isn't found.
"""

from __future__ import annotations

from typing import Optional

from .database import connection
from .models import SubtaskUpdate, TaskCreate, TaskUpdate

# Columns read back for every task. Listed explicitly (not SELECT *) so the
# response shape is stable. user_id is intentionally omitted from responses.
_TASK_COLUMNS = (
    "id, raw_text, title, category, priority, due_date, completed, created_at"
)
_SUBTASK_COLUMNS = "id, task_id, text, completed, created_at"
# Same columns, qualified for queries that join subtasks to tasks (Slice 7).
_SUBTASK_COLUMNS_S = "s.id, s.task_id, s.text, s.completed, s.created_at"


# --- Users --------------------------------------------------------------------
def create_user(email: str, password_hash: str) -> dict:
    """Insert a new user and return the row (without the hash exposed upstream)."""
    sql = "INSERT INTO users (email, password_hash) VALUES (%s, %s)"
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (email, password_hash))
            new_id = cur.lastrowid
    user = get_user_by_id(new_id)
    assert user is not None
    return user


def get_user_by_email(email: str) -> Optional[dict]:
    """Return a user row by email (includes password_hash for login checks)."""
    sql = "SELECT id, email, password_hash, created_at FROM users WHERE email = %s"
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (email,))
            return cur.fetchone()


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Return a user row by id (includes password_hash; callers don't expose it)."""
    sql = "SELECT id, email, password_hash, created_at FROM users WHERE id = %s"
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (user_id,))
            return cur.fetchone()


# --- Tasks (all scoped to a user_id) ------------------------------------------
def create_task(data: TaskCreate, user_id: int) -> dict:
    """Insert a new task owned by `user_id` and return the full persisted row."""
    sql = (
        "INSERT INTO tasks (user_id, raw_text, title, category, priority, due_date) "
        "VALUES (%s, %s, %s, %s, %s, %s)"
    )
    params = (user_id, data.raw_text, data.title, data.category, data.priority, data.due_date)
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            new_id = cur.lastrowid
    task = get_task(new_id, user_id)
    assert task is not None  # we just inserted it for this user
    return task


def list_tasks(
    user_id: int,
    category: Optional[str] = None,
    completed: Optional[bool] = None,
) -> list[dict]:
    """Return the user's tasks, optionally filtered by category and/or completed."""
    sql = f"SELECT {_TASK_COLUMNS} FROM tasks WHERE user_id = %s"
    params: list = [user_id]

    if category is not None:
        sql += " AND category = %s"
        params.append(category)
    if completed is not None:
        sql += " AND completed = %s"
        params.append(completed)

    sql += " ORDER BY created_at DESC, id DESC"
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            tasks = list(cur.fetchall())
    if tasks:  # attach subtasks in one extra query, grouped by task
        grouped = get_subtasks_for_tasks([t["id"] for t in tasks])
        for t in tasks:
            t["subtasks"] = grouped.get(t["id"], [])
    return tasks


def get_task(task_id: int, user_id: int) -> Optional[dict]:
    """Return the task if it exists AND belongs to the user, else None.

    The `user_id = %s` clause is the ownership check: another user's task is
    indistinguishable from a non-existent one, so the route returns 404 (not
    403) and never leaks whether the id exists.
    """
    sql = f"SELECT {_TASK_COLUMNS} FROM tasks WHERE id = %s AND user_id = %s"
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (task_id, user_id))
            task = cur.fetchone()
    if task is None:
        return None
    task["subtasks"] = get_subtasks_for_task(task_id)
    return task


def update_task(task_id: int, user_id: int, data: TaskUpdate) -> Optional[dict]:
    """Apply a partial update to the user's task; None if missing or not theirs."""
    fields = data.model_dump(exclude_unset=True)
    if not fields:
        return get_task(task_id, user_id)

    set_clause = ", ".join(f"{col} = %s" for col in fields)
    params = list(fields.values()) + [task_id, user_id]
    sql = f"UPDATE tasks SET {set_clause} WHERE id = %s AND user_id = %s"

    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
    return get_task(task_id, user_id)


def delete_task(task_id: int, user_id: int) -> bool:
    """Delete the user's task. True if a row was deleted, False otherwise."""
    sql = "DELETE FROM tasks WHERE id = %s AND user_id = %s"
    with connection() as conn:
        with conn.cursor() as cur:
            affected = cur.execute(sql, (task_id, user_id))
    return affected > 0


# --- Subtasks (Slice 7) -------------------------------------------------------
# Ownership is enforced by joining through `tasks` to the user_id — a subtask is
# only reachable if its parent task belongs to the requesting user.
def get_subtasks_for_task(task_id: int) -> list[dict]:
    sql = f"SELECT {_SUBTASK_COLUMNS} FROM subtasks WHERE task_id = %s ORDER BY id"
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (task_id,))
            return list(cur.fetchall())


def get_subtasks_for_tasks(task_ids: list[int]) -> dict[int, list[dict]]:
    """Fetch subtasks for many tasks in one query, grouped by task_id."""
    if not task_ids:
        return {}
    placeholders = ", ".join(["%s"] * len(task_ids))  # count is ours, not user input
    sql = f"SELECT {_SUBTASK_COLUMNS} FROM subtasks WHERE task_id IN ({placeholders}) ORDER BY id"
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, task_ids)
            rows = cur.fetchall()
    grouped: dict[int, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["task_id"], []).append(row)
    return grouped


def replace_subtasks(task_id: int, texts: list[str]) -> list[dict]:
    """Replace a task's subtasks with a fresh set (re-running breakdown is idempotent)."""
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM subtasks WHERE task_id = %s", (task_id,))
            for text in texts:
                cur.execute(
                    "INSERT INTO subtasks (task_id, text) VALUES (%s, %s)", (task_id, text)
                )
    return get_subtasks_for_task(task_id)


def get_subtask(subtask_id: int, user_id: int) -> Optional[dict]:
    """Return the subtask only if its parent task belongs to the user, else None."""
    sql = (
        f"SELECT {_SUBTASK_COLUMNS_S} FROM subtasks s "
        "JOIN tasks t ON s.task_id = t.id WHERE s.id = %s AND t.user_id = %s"
    )
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (subtask_id, user_id))
            return cur.fetchone()


def add_subtask(task_id: int, text: str) -> dict:
    """Insert one subtask under a task (ownership checked by the caller) and return it."""
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO subtasks (task_id, text) VALUES (%s, %s)", (task_id, text)
            )
            new_id = cur.lastrowid
            cur.execute(f"SELECT {_SUBTASK_COLUMNS} FROM subtasks WHERE id = %s", (new_id,))
            return cur.fetchone()


def update_subtask(subtask_id: int, user_id: int, data: SubtaskUpdate) -> Optional[dict]:
    """Partially update a subtask (completed and/or text), scoped to the owner.

    Only the fields the client actually sent are changed (exclude_unset). Column
    names come from the schema (trusted); values stay parameterized.
    """
    fields = data.model_dump(exclude_unset=True)
    if not fields:
        return get_subtask(subtask_id, user_id)
    set_clause = ", ".join(f"s.{col} = %s" for col in fields)
    params = list(fields.values()) + [subtask_id, user_id]
    sql = (
        f"UPDATE subtasks s JOIN tasks t ON s.task_id = t.id "
        f"SET {set_clause} WHERE s.id = %s AND t.user_id = %s"
    )
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
    return get_subtask(subtask_id, user_id)


def delete_subtask(subtask_id: int, user_id: int) -> bool:
    """Delete a subtask the user owns. True if a row was deleted."""
    sql = (
        "DELETE s FROM subtasks s JOIN tasks t ON s.task_id = t.id "
        "WHERE s.id = %s AND t.user_id = %s"
    )
    with connection() as conn:
        with conn.cursor() as cur:
            affected = cur.execute(sql, (subtask_id, user_id))
    return affected > 0
