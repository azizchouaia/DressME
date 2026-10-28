"""Sign up / sign in for the app: users in PostgreSQL (table `users`) + JWT.

Store: PostgreSQL when DATABASE_URL points to Postgres (infra/.env, docker compose up -d postgres);
otherwise a JSON file (ml/data/users/users.json) so the app still works without a database.

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


FIELDS = ("user_id", "name", "email", "city", "gender", "salt", "hash", "created")


def _demo_row() -> dict:
    salt = secrets.token_hex(16)
    return {"user_id": DEMO["user_id"], "name": DEMO["name"], "email": DEMO["email"], "city": DEMO["city"],
            "gender": DEMO["gender"], "salt": salt, "hash": _hash(DEMO["password"], salt), "created": time.strftime("%Y-%m-%d")}


# ---------------------------------------------------------------- PostgreSQL store
_pg_engine = None
_pg_failed = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id    TEXT PRIMARY KEY,
    email      TEXT NOT NULL UNIQUE,
    name       TEXT NOT NULL,
    city       TEXT,
    gender     TEXT,
    salt       TEXT NOT NULL,
    hash       TEXT NOT NULL,
    created    TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)"""


def sync_url(url: str) -> str:
    return url.replace("+asyncpg", "+psycopg2")


def _pg():
    """A Postgres engine when DATABASE_URL is Postgres and reachable; None -> JSON file."""
    global _pg_engine, _pg_failed
    if _pg_engine is not None or _pg_failed or os.environ.get("AUTH_STORE") == "json":
        return _pg_engine
    url = os.environ.get("DATABASE_URL") or settings.database_url
    if not url.startswith("postgresql"):
        _pg_failed = True
        return None
    try:
        from sqlalchemy import create_engine, text

        eng = create_engine(sync_url(url), future=True, pool_pre_ping=True, connect_args={"connect_timeout": 3})
        with eng.begin() as conn:
            conn.execute(text(SCHEMA))
        _pg_engine = eng
    except Exception:  # noqa: BLE001 - no database running: JSON file
        _pg_failed = True
    return _pg_engine


def _pg_get(eng, email: str) -> dict | None:
    from sqlalchemy import text

    with eng.begin() as conn:
        row = conn.execute(text(f"SELECT {', '.join(FIELDS)} FROM users WHERE email = :e"), {"e": email}).mappings().first()
        if row is None and email == DEMO["email"]:
            d = _demo_row()
            conn.execute(text(f"INSERT INTO users ({', '.join(FIELDS)}) VALUES ({', '.join(':' + f for f in FIELDS)})"
                              " ON CONFLICT DO NOTHING"), d)
            return d
        return dict(row) if row else None


# ---------------------------------------------------------------- store API (Postgres or JSON)
def _json_load() -> dict:
    users = json.loads(STORE.read_text(encoding="utf-8")) if STORE.exists() else {}
    users.setdefault(DEMO["email"], _demo_row())  # the demo account always exists
    return users


def _json_save(users: dict) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(users, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STORE)


def get_user(email: str) -> dict | None:
    eng = _pg()
    return _pg_get(eng, email) if eng else _json_load().get(email)


def insert_user(u: dict) -> bool:
    """False when the email is taken."""
    eng = _pg()
    if eng:
        from sqlalchemy import text
        from sqlalchemy.exc import IntegrityError

        try:
            with eng.begin() as conn:
                conn.execute(text(f"INSERT INTO users ({', '.join(FIELDS)}) VALUES ({', '.join(':' + f for f in FIELDS)})"), u)
            return True
        except IntegrityError:
            return False
    with _lock:
        users = _json_load()
        if u["email"] in users:
            return False
        users[u["email"]] = u
        _json_save(users)
        return True


def update_user(email: str, changes: dict) -> dict:
    eng = _pg()
    changes = {k: v for k, v in changes.items() if k in ("name", "city", "gender") and v is not None}
    if eng:
        from sqlalchemy import text

        if changes:
            with eng.begin() as conn:
                conn.execute(text(f"UPDATE users SET {', '.join(f'{k} = :{k}' for k in changes)} WHERE email = :email"),
                             {**changes, "email": email})
        return get_user(email)
    with _lock:
        users = _json_load()
        users[email].update(changes)
        _json_save(users)
        return users[email]


def store_kind() -> str:
    return "postgres" if _pg() else "json"


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
    u = get_user(claims.get("email", ""))
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
    salt = secrets.token_hex(16)
    u = {"user_id": f"usr_{uuid.uuid4().hex[:10]}", "name": inp.name.strip(), "email": email, "city": inp.city,
         "gender": inp.gender, "salt": salt, "hash": _hash(inp.password, salt), "created": time.strftime("%Y-%m-%d")}
    if not insert_user(u):
        raise HTTPException(409, "an account already uses this email")
    return {"token": token_for(u), "user": public(u)}


@router.post("/login")
def login(inp: LoginIn):
    u = get_user(inp.email.strip().lower())
    if not u or not hmac.compare_digest(u["hash"], _hash(inp.password, u["salt"])):
        raise HTTPException(401, "wrong email or password")
    return {"token": token_for(u), "user": public(u)}


@router.get("/me")
def me(authorization: str | None = Header(default=None)):
    return public(current_user(authorization))


@router.patch("/me")
def update_me(inp: ProfileIn, authorization: str | None = Header(default=None)):
    u = current_user(authorization)
    return public(update_user(u["email"], inp.model_dump()))


@router.get("/store")
def store():
    """Where accounts are kept: postgres or json."""
    return {"store": store_kind()}
