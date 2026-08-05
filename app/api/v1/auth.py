from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator
from app.auth.utils import (
    create_access_token, create_refresh_token,
    decode_token, get_current_user, verify_password,
)
from app.auth.store import create_user, get_user_by_email, revoke_token, is_revoked

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


@router.post("/signup", response_model=UserResponse, status_code=201)
async def signup(body: SignupRequest):
    try:
        user = create_user(body.email, body.username, body.password)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return UserResponse(**user)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    user = get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_data = {"sub": user["email"], "username": user["username"], "id": user["id"]}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/logout", status_code=204)
async def logout(body: RefreshRequest):
    revoke_token(body.refresh_token)
    return None


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest):
    if is_revoked(body.refresh_token):
        raise HTTPException(status_code=401, detail="Refresh token revoked")
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    revoke_token(body.refresh_token)   # rotate: old token is burned
    token_data = {k: v for k, v in payload.items() if k not in ("exp", "type")}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user)):
    user = get_user_by_email(current_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(id=user["id"], email=user["email"], username=user["username"])