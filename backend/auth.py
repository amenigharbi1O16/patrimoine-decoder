"""
Authentication — Heritage Decoder
JWT-based auth with direct bcrypt password hashing.

Flow:
  POST /api/register {username, password} → {access_token, token_type, username}
  POST /api/login    {username, password} → {access_token, token_type, username}
  Protected routes   Authorization: Bearer <token>
"""
import os
import bcrypt
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from jose import JWTError, jwt

env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(env_path)

SECRET_KEY  = os.getenv("JWT_SECRET", "heritage-decoder-secret-change-in-prod-2026")
ALGORITHM   = "HS256"
TOKEN_EXPIRE_DAYS = 30


# ─── Password helpers ─────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Hashes a plaintext password using bcrypt."""
    # Ensure password is under 72 bytes (bcrypt limit)
    pw_bytes = plain.encode('utf-8')[:72]
    hashed = bcrypt.hashpw(pw_bytes, bcrypt.gensalt())
    return hashed.decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    """Verifies a plaintext password against its bcrypt hash."""
    pw_bytes = plain.encode('utf-8')[:72]
    hashed_bytes = hashed.encode('utf-8')
    try:
        return bcrypt.checkpw(pw_bytes, hashed_bytes)
    except ValueError:
        return False


# ─── JWT helpers ──────────────────────────────────────────────────────────────

def create_access_token(username: str) -> str:
    expire = datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[str]:
    """Returns username from a valid token, or None if invalid/expired."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


# ─── FastAPI dependency ───────────────────────────────────────────────────────

from fastapi import Header, HTTPException, status


def get_current_user(authorization: str = Header(default="")) -> str:
    """
    FastAPI dependency — extract and validate Bearer token.
    Returns the authenticated username.
    Raises HTTP 401 if token is missing or invalid.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1]
    username = decode_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username
