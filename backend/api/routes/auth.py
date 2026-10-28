"""Sign up / sign in for the app (week-1 auth: JSON user store + JWT; swap the store for Postgres later).

POST /auth/register {name, email, password, city?, gender?} -> {token, user}
POST /auth/login    {email, password}                       -> {token, user}
GET  /auth/me       Authorization: Bearer <token>            -> user
PATCH /auth/me      {name?, city?, gender?}                  -> user

Demo account (rich data in every module): demo@dressme.tn / demo1234 -> user_id usr_demo.
Passwords are hashed with PBKDF2-SHA256 (200k rounds, per-user salt); never stored in clear.
"""

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from shared.config import settings

router = APIRouter(prefix="/auth", tags=["Auth"])

STORE = Path(os.environ.get("DRESSME_USERS_FILE") or Path(__file__).resolve().parents[3] / "ml" / "data" / "users" / "users.json")
TOKEN_DAYS = 30
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DEMO = {"email": "demo@dressme.tn", "password": "demo1234", "user_id": "usr_demo", "name": "Demo", "city": "Tunis",
        "gender": "female"}
_lock = threading.Lock()


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()


def _load() -> dict:
    users = json.loads(STORE.read_text(encoding="utf-8")) if STORE.exists() else {}
    if DEMO["email"] not in users:  # the demo account always exists
        salt = secrets.token_hex(16)
        users[DEMO["email"]] = {"user_id": DEMO["user_id"], "name": DEMO["name"], "email": DEMO["email"],
                                "city": DEMO["city"], "gender": DEMO["gender"], "salt": salt,
                                "hash": _hash(DEMO["password"], salt), "created": time.strftime("%Y-%m-%d")}
    return users


def _save(users: dict) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(users, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STORE)


def public(u: dict) -> dict:
    return {k: u.get(k) for k in ("user_id", "name", "email", "city", "gender", "created")}


def token_for(u: dict) -> str:
    return jwt.encode({"sub": u["user_id"], "email": u["email"], "exp": int(time.time()) + TOKEN_DAYS * 86400},
                      settings.jwt_secret, algorithm="HS256")


def current_user(authorization: str | None) -> dict:
    """The signed-in user from 'Authorization: Bearer <token>' (401 otherwise). Other routers can reuse it."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "sign in first")
    try:
        claims = jwt.decode(authorization.split(" ", 1)[1], settings.jwt_secret, algorithms=["HS256"])
    except JWTError as e:
        raise HTTPException(401, "session expired, sign in again") from e
    u = _load().get(claims.get("email", ""))
    if not u or u["user_id"] != claims.get("sub"):
        raise HTTPException(401, "unknown account")
    return u


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    email: str
    password: str = Field(min_length=6, max_length=128)
    city: str | None = "Tunis"
    gender: str | None = None


class LoginIn(BaseModel):
    email: str
    password: str


class ProfileIn(BaseModel):
    name: str | None = Field(default=None, max_length=60)
    city: str | None = None
    gender: str | None = None


@router.post("/register", status_code=201)
def register(inp: RegisterIn):
    email = inp.email.strip().lower()
    if not EMAIL.match(email):
        raise HTTPException(422, "this email does not look valid")
    with _lock:
        users = _load()
        if email in users:
            raise HTTPException(409, "an account already uses this email")
        salt = secrets.token_hex(16)
        u = {"user_id": f"usr_{uuid.uuid4().hex[:10]}", "name": inp.name.strip(), "email": email, "city": inp.city,
             "gender": inp.gender, "salt": salt, "hash": _hash(inp.password, salt), "created": time.strftime("%Y-%m-%d")}
        users[email] = u
        _save(users)
    return {"token": token_for(u), "user": public(u)}


@router.post("/login")
def login(inp: LoginIn):
    u = _load().get(inp.email.strip().lower())
    if not u or not hmac.compare_digest(u["hash"], _hash(inp.password, u["salt"])):
        raise HTTPException(401, "wrong email or password")
    return {"token": token_for(u), "user": public(u)}


@router.get("/me")
def me(authorization: str | None = Header(default=None)):
    return public(current_user(authorization))


@router.patch("/me")
def update_me(inp: ProfileIn, authorization: str | None = Header(default=None)):
    u = current_user(authorization)
    with _lock:
        users = _load()
        users[u["email"]].update({k: v for k, v in inp.model_dump().items() if v is not None})
        _save(users)
        return public(users[u["email"]])
