"""
auth.py — JWT authentication.

Two jobs:
  1. verify_user()  — check a username/password against hashed users.json,
                      and if valid, issue a signed JWT carrying the role.
  2. get_current_user() — a FastAPI dependency that reads the token from a
                      request, verifies its signature, and returns the role.

The RAG engine never sees any of this; it just receives a role string.
"""

import os
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

load_dotenv()

# Secret used to SIGN tokens. Only the server knows it, so only the server
# can create valid tokens — that's what makes the role tamper-proof.
SECRET_KEY = os.getenv("JWT_SECRET")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET not found. Add it to your .env file.")

ALGORITHM = "HS256"          # signing algorithm
TOKEN_EXPIRE_MINUTES = 60    # tokens auto-expire after 1 hour

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTPBearer tells FastAPI to look for "Authorization: Bearer <token>".
bearer_scheme = HTTPBearer()

USERS_PATH = Path(__file__).resolve().parent.parent.parent / "users.json"
with open(USERS_PATH) as f:
    USERS = json.load(f)


def verify_user(username: str, password: str) -> dict:
    """Check credentials against hashed users.json.

    Returns {"username", "role"} if valid, else raises 401.
    """
    user = USERS.get(username)
    # pwd_context.verify hashes the typed password and compares to the stored
    # hash. Same input -> same hash -> match; the stored hash never reveals
    # the original password.
    if not user or not pwd_context.verify(password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    return {"username": username, "role": user["role"]}


def create_token(username: str, role: str) -> str:
    """Create a signed JWT containing the username, role, and expiry."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": username,   # 'sub' (subject) = who the token is about
        "role": role,      # the role is baked in and signed
        "exp": expire,     # expiry — jose enforces this automatically
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """FastAPI dependency: validate the token, return {"username", "role"}.

    Any endpoint that depends on this is protected — it only runs if a valid,
    unexpired token is presented.
    """
    token = credentials.credentials
    try:
        # decode() verifies the signature AND the expiry. If either fails
        # (tampered token, expired, wrong secret), it raises JWTError.
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return {"username": payload["sub"], "role": payload["role"]}