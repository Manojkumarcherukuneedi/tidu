"""MySQL connection handling for the AI Task Organizer.

All database access goes through this module. It reads connection settings
from environment variables (loaded from a local .env file in development),
exposes a `get_connection()` helper for callers, and provides `init_db()` to
create the database/table on startup and `check_connection()` for health checks.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

import pymysql
from dotenv import load_dotenv

# Load .env once at import time. In production the real environment wins.
load_dotenv()


def _db_settings() -> dict:
    """Connection settings for the application database (incl. db name)."""
    return {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "ai_task_organizer"),
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": True,
    }


def get_connection() -> pymysql.connections.Connection:
    """Open a new connection to the application database.

    Callers are responsible for closing it; prefer the `connection()` context
    manager below, which closes automatically.
    """
    return pymysql.connect(**_db_settings())


@contextmanager
def connection():
    """Context manager that yields a connection and always closes it."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


# Users own tasks (Slice 6).
CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

# Each task belongs to a user. ON DELETE CASCADE removes a user's tasks with them.
CREATE_TASKS_TABLE = """
CREATE TABLE IF NOT EXISTS tasks (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT NOT NULL,
    raw_text    TEXT,
    title       VARCHAR(255),
    category    VARCHAR(50),
    priority    VARCHAR(20),
    due_date    DATE,
    completed   BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

# AI-generated subtasks belong to a task (Slice 7). Cascade-deleted with it.
CREATE_SUBTASKS_TABLE = """
CREATE TABLE IF NOT EXISTS subtasks (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    task_id     INT NOT NULL,
    text        VARCHAR(500) NOT NULL,
    completed   BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


def _tasks_table_is_legacy(cur, db_name: str) -> bool:
    """True if a `tasks` table exists but predates the `user_id` column."""
    cur.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM information_schema.tables
             WHERE table_schema = %s AND table_name = 'tasks') AS has_table,
          (SELECT COUNT(*) FROM information_schema.columns
             WHERE table_schema = %s AND table_name = 'tasks'
               AND column_name = 'user_id') AS has_user_id
        """,
        (db_name, db_name),
    )
    row = cur.fetchone()
    return bool(row["has_table"]) and not bool(row["has_user_id"])


def init_db() -> None:
    """Create the database (if missing), the `users` table, and the `tasks` table.

    Slice 6 migration: the original `tasks` table had no `user_id`. Since the
    brief allows wiping existing (test) tasks, we drop a legacy `tasks` table so
    it can be recreated with the foreign key. This runs only once — after the
    new column exists, the check is false and nothing is dropped on restart.
    """
    settings = _db_settings()
    db_name = settings.pop("database")

    # 1. Ensure the database exists.
    server_conn = pymysql.connect(**settings)
    try:
        with server_conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
    finally:
        server_conn.close()

    with connection() as conn:
        with conn.cursor() as cur:
            # 2. One-time migration: drop the pre-auth tasks table if present.
            if _tasks_table_is_legacy(cur, db_name):
                cur.execute("DROP TABLE tasks;")
            # 3. Create tables. Users first — tasks' foreign key references it,
            #    and subtasks reference tasks.
            cur.execute(CREATE_USERS_TABLE)
            cur.execute(CREATE_TASKS_TABLE)
            cur.execute(CREATE_SUBTASKS_TABLE)


def check_connection() -> bool:
    """Return True if the application database is reachable, else False."""
    try:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        return True
    except Exception:
        return False
