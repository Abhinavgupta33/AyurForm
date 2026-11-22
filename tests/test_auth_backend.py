from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from auth_api import create_app
from auth_db import connect, migrate
from auth_service import ACCESS_COOKIE, AUDIENCE, CSRF_COOKIE, ISSUER, REFRESH_COOKIE, AuthSettings, AuthService, verify_password


SECRET = "test-signing-secret-that-is-at-least-thirty-two-characters-long"
ORIGIN = "http://localhost:8501"


@pytest.fixture()
def auth_client(tmp_path):
    settings = AuthSettings(db_path=tmp_path / "auth-test.db", jwt_secret=SECRET, cookie_secure=False, allowed_origin=ORIGIN)
    with TestClient(create_app(settings, migrate_database=False), base_url="http://localhost:8000", client=("127.0.0.1", 51234)) as client:
        yield client, settings


def signup(client, *, email="reader@example.com", password="CorrectHorseBattery1!", full_name="Reader One"):
    return client.post("/auth/signup", json={"full_name": full_name, "email": email, "password": password}, headers={"Origin": ORIGIN})


def csrf_headers(client):
    return {"Origin": ORIGIN, "X-CSRF-Token": client.cookies.get(CSRF_COOKIE)}


def test_signup_hashes_password_and_sets_secure_cookie_shape(auth_client):
    client, settings = auth_client
    response = signup(client)
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "reader@example.com"
    assert "password" not in response.text and "access" not in response.json()
    header = response.headers.get_list("set-cookie")
    access = next(value.lower() for value in header if value.startswith(f"{ACCESS_COOKIE}="))
    refresh = next(value.lower() for value in header if value.startswith(f"{REFRESH_COOKIE}="))
    assert "httponly" in access and "samesite=lax" in access and "path=/" in access
    assert "secure" not in access and "domain=" not in access
    assert "httponly" in refresh
    with connect(settings.db_path) as db:
        password_hash = db.execute("SELECT password_hash FROM users WHERE email='reader@example.com'").fetchone()[0]
    assert password_hash != "CorrectHorseBattery1!"
    assert verify_password(password_hash, "CorrectHorseBattery1!")


def test_signup_duplicate_and_password_policy(auth_client):
    client, _ = auth_client
    assert signup(client).status_code == 200
    assert signup(client).status_code == 409
    weak = signup(client, email="weak@example.com", password="onlylowercase")
    assert weak.status_code == 422


def test_login_success_and_generic_invalid_credentials(auth_client):
    client, _ = auth_client
    signup(client)
    valid = client.post("/auth/login", json={"email": "READER@example.com", "password": "CorrectHorseBattery1!"}, headers={"Origin": ORIGIN})
    assert valid.status_code == 200
    invalid = client.post("/auth/login", json={"email": "reader@example.com", "password": "WrongPassword1!"}, headers={"Origin": ORIGIN})
    assert invalid.status_code == 401
    assert invalid.json()["detail"]["code"] == "invalid_credentials"
    unknown = client.post("/auth/login", json={"email": "missing@example.com", "password": "WrongPassword1!"}, headers={"Origin": ORIGIN})
    assert unknown.status_code == 401
    assert unknown.json()["detail"] == invalid.json()["detail"]


def test_access_token_validation_expiry_and_claim_checks(auth_client):
    client, settings = auth_client
    signup(client)
    assert client.get("/auth/me").status_code == 200
    now = datetime.now(timezone.utc)
    base = {"sub": "1", "sid": "missing", "jti": "test", "iat": now, "nbf": now, "exp": now + timedelta(minutes=1)}
    expired = jwt.encode(base | {"iss": ISSUER, "aud": AUDIENCE, "exp": now - timedelta(seconds=1)}, SECRET, algorithm="HS256")
    assert client.get("/auth/me", cookies={ACCESS_COOKIE: expired}).status_code == 401
    wrong_issuer = jwt.encode(base | {"iss": "wrong", "aud": AUDIENCE}, SECRET, algorithm="HS256")
    assert client.get("/auth/me", cookies={ACCESS_COOKIE: wrong_issuer}).status_code == 401
    wrong_audience = jwt.encode(base | {"iss": ISSUER, "aud": "wrong"}, SECRET, algorithm="HS256")
    assert client.get("/auth/me", cookies={ACCESS_COOKIE: wrong_audience}).status_code == 401
    forged = jwt.encode(base | {"iss": ISSUER, "aud": AUDIENCE}, "another-signing-secret-that-is-long-enough", algorithm="HS256")
    assert client.get("/auth/me", cookies={ACCESS_COOKIE: forged}).status_code == 401


def test_refresh_rotation_and_reuse_revokes_session(auth_client):
    client, _ = auth_client
    signup(client)
    old_refresh, old_csrf = client.cookies.get(REFRESH_COOKIE), client.cookies.get(CSRF_COOKIE)
    rotated = client.post("/auth/refresh", headers=csrf_headers(client))
    assert rotated.status_code == 200
    new_refresh = client.cookies.get(REFRESH_COOKIE)
    assert new_refresh != old_refresh
    replay = client.post("/auth/refresh", cookies={REFRESH_COOKIE: old_refresh, CSRF_COOKIE: old_csrf}, headers={"Origin": ORIGIN, "X-CSRF-Token": old_csrf})
    assert replay.status_code == 401
    assert replay.json()["detail"]["code"] == "refresh_reuse"
    assert client.get("/auth/me").status_code == 401


def test_logout_revokes_and_clears_cookie(auth_client):
    client, _ = auth_client
    signup(client)
    logout = client.post("/auth/logout", headers=csrf_headers(client))
    assert logout.status_code == 204
    assert "max-age=0" in ",".join(logout.headers.get_list("set-cookie")).lower()
    assert client.get("/auth/me").status_code == 401


def test_csrf_required_for_cookie_authenticated_mutations(auth_client):
    client, _ = auth_client
    signup(client)
    assert client.patch("/auth/me", json={"full_name": "Changed Name"}).status_code == 403
    updated = client.patch("/auth/me", json={"full_name": "Changed Name"}, headers=csrf_headers(client))
    assert updated.status_code == 200
    assert updated.json()["user"]["full_name"] == "Changed Name"
    assert client.post("/auth/refresh", headers={"Origin": ORIGIN, "X-CSRF-Token": "wrong"}).status_code == 403


def test_rate_limit_is_local_process_only(auth_client):
    client, _ = auth_client
    for index in range(5):
        result = client.post("/auth/login", json={"email": "limit@example.com", "password": "WrongPassword1!"}, headers={"Origin": ORIGIN})
        assert result.status_code == 401
    blocked = client.post("/auth/login", json={"email": "limit@example.com", "password": "WrongPassword1!"}, headers={"Origin": ORIGIN})
    assert blocked.status_code == 429


def test_migration_preserves_legacy_rows_and_leaves_them_unassigned(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE analyses(id INTEGER PRIMARY KEY, created_at TEXT, query TEXT, payload TEXT)")
        db.execute("CREATE TABLE saved_refs(id INTEGER PRIMARY KEY, created_at TEXT, passage_id TEXT UNIQUE, reference TEXT, text TEXT, metadata TEXT)")
        db.execute("INSERT INTO analyses(id,created_at,query,payload) VALUES(7,'old','query','{}')")
        db.execute("INSERT INTO saved_refs(id,created_at,passage_id,reference,text,metadata) VALUES(9,'old','passage','ref','text','{}')")
    assert migrate(path, create_backup=True) == 1
    backups = list((tmp_path / "backups").glob("legacy.pre_auth_*.db"))
    assert len(backups) == 1
    with connect(path) as db:
        assert tuple(db.execute("SELECT id,user_id FROM analyses").fetchone()) == (7, None)
        assert tuple(db.execute("SELECT id,user_id FROM saved_refs").fetchone()) == (9, None)
        assert db.execute("SELECT version FROM schema_migrations").fetchone()[0] == 1
        assert {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")} >= {"users", "auth_sessions", "auth_refresh_tokens"}


def test_missing_secret_fails_securely(tmp_path):
    settings = AuthSettings(db_path=tmp_path / "missing-secret.db", jwt_secret=None, cookie_secure=False)
    with TestClient(create_app(settings, migrate_database=False)) as client:
        response = client.post("/auth/signup", json={"full_name": "Name", "email": "person@example.com", "password": "CorrectHorseBattery1!"})
    assert response.status_code == 503
