"""Authentication: password hashing, JWT issuing/verification, and the
`get_current_user` dependency that protects the task routes.

Security choices (worth knowing for interviews):
  - Passwords are hashed with **bcrypt**, a vetted, deliberately-slow adaptive
    hash with a per-password random salt baked into the output. We never store
    or log the plaintext password. We don't roll our own crypto.
  - Auth is **stateless** via a signed **JWT**. On login we issue a token whose
    payload carries the user id (`sub`) and an expiry (`exp`), signed with a
    secret from the environment (HS256). On each request we verify the
    signature + expiry and trust the claims — no server-side session store.
  - The signing secret comes from `JWT_SECRET` (env), never hardcoded.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import crud

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", str(60 * 24 * 7)))  # 7 days

# auto_error=False so a MISSING token reaches our handler as None and we can
# return a 401 (HTTPBearer's default would be a 403).
_bearer = HTTPBearer(auto_error=False)


# --- Password hashing ---------------------------------------------------------
def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt (random salt included in output)."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, password_hash: str) -> bool:
    """Constant-time check of a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --- JWT ----------------------------------------------------------------------
def create_access_token(user_id: int) -> str:
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET is not set in the environment")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    """Decode + validate a JWT, or raise 401 for invalid/expired tokens."""
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET is not set in the environment")
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# --- Dependency ---------------------------------------------------------------
def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Resolve the current user from the Bearer token, or 401.

    Rejects missing, malformed, invalid, and expired tokens, and tokens whose
    user no longer exists.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or not credentials.credentials:
        raise unauthorized

    payload = _decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if user_id is None:
        raise unauthorized

    user = crud.get_user_by_id(int(user_id))
    if user is None:
        raise unauthorized
    return user
