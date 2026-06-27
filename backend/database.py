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


# Schema for slice 1. Matches the data model in the project brief exactly.
CREATE_TASKS_TABLE = """
CREATE TABLE IF NOT EXISTS tasks (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    raw_text    TEXT,
    title       VARCHAR(255),
    category    VARCHAR(50),
    priority    VARCHAR(20),
    due_date    DATE,
    completed   BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


def init_db() -> None:
    """Create the database (if missing) and the `tasks` table.

    Connects first without selecting a database so it can issue
    CREATE DATABASE, then connects to the database to create the table.
    Raises on failure so the caller can decide how to handle it.
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

    # 2. Ensure the tasks table exists.
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_TASKS_TABLE)


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
