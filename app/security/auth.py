# app/security/auth.py

from datetime import datetime, timedelta
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext
import redis.asyncio as redis

from app.settings import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Redis client for refresh token revocation blocklist
_redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
_REVOKED_PREFIX = "revoked_token:"
_REVOKED_TTL = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400  # seconds


# ----------------------------------------------------------------
# Password hashing
# ----------------------------------------------------------------
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ----------------------------------------------------------------
# JWT — both functions accept a plain dict so the router
# can just pass token_data = {"sub": user.id, "username": ...}
# without caring about the internal payload structure.
# ----------------------------------------------------------------
def create_access_token(token_data: dict) -> str:
    payload = {
        **token_data,
        "type": "access",
        "exp": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(token_data: dict) -> str:
    payload = {
        **token_data,
        "type": "refresh",
        "exp": datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


# ----------------------------------------------------------------
# Token revocation — refresh tokens are blocklisted in Redis
# until they naturally expire (same TTL as the token itself).
# ----------------------------------------------------------------
async def revoke_token(token: str) -> None:
    await _redis.set(f"{_REVOKED_PREFIX}{token}", "1", ex=_REVOKED_TTL)


async def is_revoked(token: str) -> bool:
    return await _redis.get(f"{_REVOKED_PREFIX}{token}") is not None


# ----------------------------------------------------------------
# User CRUD — async, DB-backed.
# Thin helpers used only by the auth router.
# ----------------------------------------------------------------
async def create_user(db, email: str, username: str, password: str):
    """
    Inserts a new User row. Raises ValueError (→ 409 in the router)
    if email or username is already taken.
    """
    from sqlalchemy import select
    from app.db.models import User

    if (await db.execute(select(User).where(User.email == email))).scalar_one_or_none():
        raise ValueError("Email already registered")

    if (await db.execute(select(User).where(User.username == username))).scalar_one_or_none():
        raise ValueError("Username already taken")

    user = User(
        email=email,
        username=username,
        hashed_password=hash_password(password),
        auth_provider="password",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_email(db, email: str):
    """Returns the User ORM object or None."""
    from sqlalchemy import select
    from app.db.models import User

    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()