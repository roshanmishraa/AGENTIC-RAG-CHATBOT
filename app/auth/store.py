import uuid
from typing import Optional
from app.auth.utils import hash_password

_USERS: dict = {}
_REVOKED_TOKENS: set = set()

def create_user(email: str, username: str, plain_password: str) -> dict:
    if email in _USERS:
        raise ValueError("Email already registered")
    user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "username": username,
        "hashed_password": hash_password(plain_password),
    }
    _USERS[email] = user
    return {k: v for k, v in user.items() if k != "hashed_password"}

def get_user_by_email(email: str) -> Optional[dict]:
    return _USERS.get(email)

def revoke_token(token: str):
    _REVOKED_TOKENS.add(token)

def is_revoked(token: str) -> bool:
    return token in _REVOKED_TOKENS