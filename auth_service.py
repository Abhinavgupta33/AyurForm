"""Authentication policy, credentials, JWT validation and session rotation."""
from __future__ import annotations

import hmac
import os
import secrets
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from argon2.low_level import Type

from auth_db import DEFAULT_DB_PATH, connect, migrate, sha256, utc_now

ACCESS_COOKIE = "ayursutra_access"
REFRESH_COOKIE = "ayursutra_refresh"
CSRF_COOKIE = "ayursutra_csrf"
ALGORITHM = "HS256"
ISSUER = "ayursutra-ai"
AUDIENCE = "ayursutra-web"
ACCESS_LIFETIME = timedelta(minutes=15)
REFRESH_LIFETIME = timedelta(days=7)
PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16, type=Type.ID)


class AuthError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 401):
        self.code, self.message, self.status_code = code, message, status_code
        super().__init__(message)


@dataclass(frozen=True)
class AuthSettings:
    db_path: Path = DEFAULT_DB_PATH
    jwt_secret: str | None = None
    cookie_secure: bool = True
    allowed_origin: str = "http://localhost:8501"

    @classmethod
    def from_env(cls) -> "AuthSettings":
        environment = os.getenv("AYURSUTRA_ENV", "").casefold()
        explicit_local_http = environment == "development" and os.getenv("AYURSUTRA_AUTH_COOKIE_SECURE") == "0"
        return cls(
            db_path=Path(os.getenv("AYURSUTRA_AUTH_DB_PATH", str(DEFAULT_DB_PATH))),
            jwt_secret=os.getenv("AYURSUTRA_AUTH_JWT_SECRET") or None,
            cookie_secure=not explicit_local_http,
            allowed_origin=os.getenv("AYURSUTRA_AUTH_ALLOWED_ORIGIN", "http://localhost:8501"),
        )


def normalize_email(email: str) -> str:
    result = email.strip().casefold()
    if len(result) > 254 or "@" not in result or result.startswith("@") or result.endswith("@"):
        raise AuthError("invalid_input", "Provide a valid email address.", 422)
    return result


def validate_full_name(value: str) -> str:
    result = " ".join(value.split())
    if not 1 <= len(result) <= 120:
        raise AuthError("invalid_input", "Full name must contain 1 to 120 characters.", 422)
    return result


def validate_password(password: str) -> None:
    if not 12 <= len(password) <= 128:
        raise AuthError("invalid_input", "Password must contain 12 to 128 characters.", 422)
    classes = sum((any(char.islower() for char in password), any(char.isupper() for char in password), any(char.isdigit() for char in password), any(not char.isalnum() for char in password)))
    if classes < 3:
        raise AuthError("invalid_input", "Password must use at least three character types.", 422)


def hash_password(password: str) -> str:
    validate_password(password)
    return PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


class AuthService:
    def __init__(self, settings: AuthSettings):
        self.settings = settings

    def require_configured(self) -> None:
        if not self.settings.jwt_secret or len(self.settings.jwt_secret) < 32:
            raise AuthError("auth_unavailable", "Authentication is not configured.", 503)

    def initialize(self, *, create_backup: bool = True) -> None:
        self.require_configured()
        migrate(self.settings.db_path, create_backup=create_backup)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _user_response(self, user: sqlite3.Row | dict) -> dict:
        response = {"id": user["id"], "full_name": user["full_name"], "email": user["email"], "is_active": bool(user["is_active"])}
        if "created_at" in user.keys():
            response["created_at"] = user["created_at"]
        return response

    def _new_session(self, db: sqlite3.Connection, user_id: int) -> tuple[str, str, str]:
        now = self._now()
        session_id, family_id = str(uuid.uuid4()), str(uuid.uuid4())
        raw_refresh, raw_csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
        refresh_hash = sha256(raw_refresh)
        expiry = (now + REFRESH_LIFETIME).isoformat()
        db.execute("INSERT INTO auth_sessions(id,user_id,refresh_token_hash,csrf_token_hash,token_family_id,created_at,expires_at,last_used_at) VALUES(?,?,?,?,?,?,?,?)", (session_id, user_id, refresh_hash, sha256(raw_csrf), family_id, now.isoformat(), expiry, now.isoformat()))
        db.execute("INSERT INTO auth_refresh_tokens(token_hash,session_id,issued_at) VALUES(?,?,?)", (refresh_hash, session_id, now.isoformat()))
        return session_id, f"{session_id}.{raw_refresh}", raw_csrf

    def _access_token(self, user_id: int, session_id: str) -> str:
        now = self._now()
        payload = {"sub": str(user_id), "sid": session_id, "jti": str(uuid.uuid4()), "iss": ISSUER, "aud": AUDIENCE, "iat": now, "nbf": now, "exp": now + ACCESS_LIFETIME}
        return jwt.encode(payload, self.settings.jwt_secret, algorithm=ALGORITHM)

    def signup(self, full_name: str, email: str, password: str) -> tuple[dict, str, str, str]:
        self.require_configured()
        name, normalized_email, password_hash = validate_full_name(full_name), normalize_email(email), hash_password(password)
        with connect(self.settings.db_path) as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                now = utc_now()
                cursor = db.execute("INSERT INTO users(full_name,email,password_hash,is_active,created_at,updated_at) VALUES(?,?,?,?,?,?)", (name, normalized_email, password_hash, 1, now, now))
                user_id = int(cursor.lastrowid)
                sid, refresh, csrf = self._new_session(db, user_id)
                user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
                db.commit()
            except sqlite3.IntegrityError:
                db.rollback()
                raise AuthError("email_unavailable", "Unable to create this account.", 409) from None
        return self._user_response(user), self._access_token(user_id, sid), refresh, csrf

    def login(self, email: str, password: str) -> tuple[dict, str, str, str]:
        self.require_configured()
        normalized_email = normalize_email(email)
        with connect(self.settings.db_path) as db:
            user = db.execute("SELECT * FROM users WHERE email=?", (normalized_email,)).fetchone()
            # Execute an Argon2 verification even for an unknown account, reducing timing variance.
            valid = bool(user and user["is_active"] and verify_password(user["password_hash"], password))
            if not valid:
                if not user:
                    verify_password(PASSWORD_HASHER.hash("invalid-password-placeholder-A1!"), password)
                raise AuthError("invalid_credentials", "Invalid email or password.", 401)
            db.execute("BEGIN IMMEDIATE")
            sid, refresh, csrf = self._new_session(db, int(user["id"]))
            db.commit()
        return self._user_response(user), self._access_token(int(user["id"]), sid), refresh, csrf

    def _parse_refresh(self, refresh: str | None) -> tuple[str, str]:
        if not refresh or "." not in refresh:
            raise AuthError("invalid_session", "Authentication is required.")
        session_id, raw = refresh.split(".", 1)
        try:
            uuid.UUID(session_id)
        except ValueError:
            raise AuthError("invalid_session", "Authentication is required.") from None
        if not raw:
            raise AuthError("invalid_session", "Authentication is required.")
        return session_id, raw

    def _csrf_ok(self, db: sqlite3.Connection, session: sqlite3.Row, csrf: str | None) -> bool:
        return bool(csrf and hmac.compare_digest(sha256(csrf), session["csrf_token_hash"]))

    def refresh(self, refresh_cookie: str | None, csrf: str | None) -> tuple[dict, str, str, str]:
        self.require_configured()
        session_id, raw = self._parse_refresh(refresh_cookie)
        token_hash = sha256(raw)
        with connect(self.settings.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            session = db.execute("SELECT s.*, u.full_name,u.email,u.is_active,u.created_at FROM auth_sessions s JOIN users u ON u.id=s.user_id WHERE s.id=?", (session_id,)).fetchone()
            if not session or session["revoked_at"] or session["expires_at"] <= utc_now() or not session["is_active"]:
                db.rollback(); raise AuthError("invalid_session", "Authentication is required.")
            if not self._csrf_ok(db, session, csrf):
                db.rollback(); raise AuthError("csrf_failed", "Invalid request origin or CSRF token.", 403)
            token = db.execute("SELECT * FROM auth_refresh_tokens WHERE token_hash=? AND session_id=?", (token_hash, session_id)).fetchone()
            if not token or token["revoked_at"]:
                db.rollback(); raise AuthError("invalid_session", "Authentication is required.")
            if token["used_at"]:
                now = utc_now()
                db.execute("UPDATE auth_sessions SET revoked_at=?, reuse_detected_at=? WHERE token_family_id=? AND revoked_at IS NULL", (now, now, session["token_family_id"]))
                db.execute("UPDATE auth_refresh_tokens SET revoked_at=? WHERE session_id=? AND revoked_at IS NULL", (now, session_id))
                db.commit()
                raise AuthError("refresh_reuse", "Authentication is required.")
            now = self._now()
            raw_next = secrets.token_urlsafe(48)
            # Keep the double-submit CSRF value for the lifetime of the server-side session.
            # This permits a replayed old refresh credential to reach reuse detection.
            csrf_next = csrf
            hash_next = sha256(raw_next)
            db.execute("UPDATE auth_refresh_tokens SET used_at=? WHERE token_hash=?", (now.isoformat(), token_hash))
            db.execute("INSERT INTO auth_refresh_tokens(token_hash,session_id,issued_at) VALUES(?,?,?)", (hash_next, session_id, now.isoformat()))
            db.execute("UPDATE auth_sessions SET refresh_token_hash=?,last_used_at=? WHERE id=?", (hash_next, now.isoformat(), session_id))
            db.commit()
        return self._user_response(session), self._access_token(int(session["user_id"]), session_id), f"{session_id}.{raw_next}", csrf_next

    def principal(self, access_cookie: str | None) -> dict:
        self.require_configured()
        if not access_cookie:
            raise AuthError("invalid_session", "Authentication is required.")
        try:
            claims = jwt.decode(access_cookie, self.settings.jwt_secret, algorithms=[ALGORITHM], issuer=ISSUER, audience=AUDIENCE, options={"require": ["sub", "sid", "jti", "exp", "iat", "nbf"]})
            user_id, session_id = int(claims["sub"]), str(claims["sid"])
        except (jwt.InvalidTokenError, ValueError):
            raise AuthError("invalid_session", "Authentication is required.") from None
        with connect(self.settings.db_path) as db:
            user = db.execute("SELECT u.* FROM users u JOIN auth_sessions s ON s.user_id=u.id WHERE u.id=? AND s.id=? AND s.revoked_at IS NULL AND s.expires_at>? AND u.is_active=1", (user_id, session_id, utc_now())).fetchone()
        if not user:
            raise AuthError("invalid_session", "Authentication is required.")
        return self._user_response(user) | {"session_id": session_id}

    def update_profile(self, access_cookie: str | None, csrf: str | None, full_name: str) -> dict:
        principal = self.principal(access_cookie)
        name = validate_full_name(full_name)
        with connect(self.settings.db_path) as db:
            session = db.execute("SELECT * FROM auth_sessions WHERE id=?", (principal["session_id"],)).fetchone()
            if not session or not self._csrf_ok(db, session, csrf):
                raise AuthError("csrf_failed", "Invalid request origin or CSRF token.", 403)
            now = utc_now()
            db.execute("UPDATE users SET full_name=?, updated_at=? WHERE id=?", (name, now, principal["id"]))
            db.commit()
            user = db.execute("SELECT * FROM users WHERE id=?", (principal["id"],)).fetchone()
        return self._user_response(user)

    def logout(self, refresh_cookie: str | None, csrf: str | None) -> None:
        self.require_configured()
        session_id, _ = self._parse_refresh(refresh_cookie)
        with connect(self.settings.db_path) as db:
            session = db.execute("SELECT * FROM auth_sessions WHERE id=?", (session_id,)).fetchone()
            if session and not self._csrf_ok(db, session, csrf):
                raise AuthError("csrf_failed", "Invalid request origin or CSRF token.", 403)
            if session:
                now = utc_now()
                db.execute("UPDATE auth_sessions SET revoked_at=COALESCE(revoked_at, ?) WHERE id=?", (now, session_id))
                db.execute("UPDATE auth_refresh_tokens SET revoked_at=COALESCE(revoked_at, ?) WHERE session_id=?", (now, session_id))
                db.commit()
