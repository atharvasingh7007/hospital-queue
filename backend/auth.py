"""
Hospital Queue AI — Authentication & Authorization
JWT-based auth with role-based access control for patients, doctors, and admins.
"""
import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import AppConfig
from database import get_db

logger = logging.getLogger("hospital_queue.auth")

# ── Password Hashing ──────────────────────────────────

def hash_password(plain: str) -> str:
    """Hash a password with a random salt using SHA-256."""
    salt = os.urandom(16).hex()
    hashed = hashlib.sha256(f"{salt}:{plain}".encode()).hexdigest()
    return f"{salt}${hashed}"

def verify_password(plain: str, stored: str) -> bool:
    """Verify a password against the stored hash."""
    try:
        salt, hashed = stored.split("$", 1)
        check = hashlib.sha256(f"{salt}:{plain}".encode()).hexdigest()
        return check == hashed
    except ValueError:
        return False



# ── JWT Token Management ──────────────────────────────

ALGORITHM = "HS256"
TOKEN_EXPIRY_HOURS = 24

def create_token(user_id: int, role: str, name: str) -> str:
    """Generate a signed JWT token."""
    payload = {
        "sub": str(user_id),
        "role": role,
        "name": name,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, AppConfig.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Verify and decode a JWT token. Raises on invalid/expired."""
    try:
        payload = jwt.decode(token, AppConfig.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ── Request / Response Models ─────────────────────────

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=120)
    password: str = Field(..., min_length=6, max_length=128)
    phone: str = Field(..., min_length=10, max_length=15)
    role: str = Field(default="patient", pattern="^(patient|doctor|admin)$")
    # Optional fields for specific roles
    age: Optional[int] = Field(None, ge=0, le=150)
    gender: Optional[str] = None
    specialty: Optional[str] = None
    department_id: Optional[int] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user: dict
    message: str


class UserInfo(BaseModel):
    id: int
    name: str
    email: str
    role: str
    linked_id: Optional[int] = None


# ── Dependencies ──────────────────────────────────────

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[dict]:
    """Extract current user from JWT token. Returns None if no token."""
    if credentials is None:
        return None
    payload = decode_token(credentials.credentials)
    return {
        "user_id": int(payload["sub"]),
        "role": payload["role"],
        "name": payload["name"],
    }


async def require_auth(
    user: Optional[dict] = Depends(get_current_user),
) -> dict:
    """Require valid authentication. Raises 401 if not authenticated."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_doctor(user: dict = Depends(require_auth)) -> dict:
    """Require doctor role."""
    if user["role"] not in ("doctor", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Doctor access required",
        )
    return user


async def require_admin(user: dict = Depends(require_auth)) -> dict:
    """Require admin role."""
    if user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
