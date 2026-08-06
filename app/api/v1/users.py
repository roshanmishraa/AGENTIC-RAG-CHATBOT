# app/api/v1/users.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import User
from app.security.rbac import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = None
    phone_number: str | None = None
    username: str | None = None          # ← ADDED — was missing entirely


@router.get("/me")
async def get_my_profile(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,       # ← ADDED — now matches /auth/me response
        "full_name": user.full_name,
        "phone_number": user.phone_number,
        "role": user.role.value,
        "auth_provider": user.auth_provider,
        "created_at": user.created_at,
    }


@router.patch("/me")
async def update_my_profile(
    payload: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Username change needs a uniqueness check —
    # two users can't have the same username.
    if payload.username is not None:
        existing = await db.execute(
            select(User).where(
                User.username == payload.username,
                User.id != user.id,          # exclude self
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Username already taken")
        user.username = payload.username

    if payload.full_name is not None:
        user.full_name = payload.full_name

    if payload.phone_number is not None:
        user.phone_number = payload.phone_number

    await db.commit()
    return {
        "status": "updated",
        "username": user.username,
        "full_name": user.full_name,
        "phone_number": user.phone_number,
    }