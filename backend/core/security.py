from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from core.config import settings

# ──────────────────────────────────────────────
# Password hashing (bcrypt)
# ──────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return bcrypt hash of a plain-text password."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches the stored hash."""
    return pwd_context.verify(plain, hashed)


# ──────────────────────────────────────────────
# JWT token schemas
# ──────────────────────────────────────────────

class TokenPayload(BaseModel):
    sub:   str            # user id (as string)
    type:  str            # "access" | "refresh"
    exp:   Optional[int]  # Unix timestamp


class TokenPair(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"


# ──────────────────────────────────────────────
# Token creation
# ──────────────────────────────────────────────

def _create_token(subject: int, token_type: str, expires_delta: timedelta) -> str:
    expire = datetime.utcnow() + expires_delta
    payload = {
        "sub":  str(subject),
        "type": token_type,
        "exp":  expire,
        "iat":  datetime.utcnow(),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: int) -> str:
    return _create_token(
        subject=user_id,
        token_type="access",
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: int) -> str:
    return _create_token(
        subject=user_id,
        token_type="refresh",
        expires_delta=timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES),
    )


def create_token_pair(user_id: int) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


# ──────────────────────────────────────────────
# Token verification
# ──────────────────────────────────────────────

def decode_token(token: str) -> TokenPayload:
    """
    Decode and validate a JWT token.
    Raises jose.JWTError on invalid / expired tokens.
    """
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    return TokenPayload(**payload)


def verify_access_token(token: str) -> TokenPayload:
    data = decode_token(token)
    if data.type != "access":
        raise JWTError("Invalid token type")
    return data


def verify_refresh_token(token: str) -> TokenPayload:
    data = decode_token(token)
    if data.type != "refresh":
        raise JWTError("Invalid token type")
    return data
