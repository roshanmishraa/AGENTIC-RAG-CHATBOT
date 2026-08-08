# app/api/v1/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.security.auth import (
    create_access_token, create_refresh_token,
    decode_token, verify_password,
    create_user, get_user_by_email,
    revoke_token, is_revoked,
)
from app.security.rbac import get_current_user   # ← correct source

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    username: str
    password: str

    @field_validator("password")
    @classmethod
    def strong_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Need at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Need at least one digit")
        return v

    @field_validator("username")
    @classmethod
    def valid_username(cls, v):
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    username: str



@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    try:
        user = await create_user(db, body.email, body.username, body.password)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    
    token_data = {"sub": user.id, "username": user.username}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_email(db, body.email)
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_data = {"sub": user.id, "username": user.username}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/logout", status_code=204)
async def logout(body: RefreshRequest):
    await revoke_token(body.refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest):
    if await is_revoked(body.refresh_token):
        raise HTTPException(status_code=401, detail="Refresh token revoked")
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    await revoke_token(body.refresh_token)
    token_data = {k: v for k, v in payload.items() if k not in ("exp", "type")}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user=Depends(get_current_user)):
    # get_current_user from rbac.py already returns the User ORM object
    return UserResponse(id=current_user.id, email=current_user.email, username=current_user.username)