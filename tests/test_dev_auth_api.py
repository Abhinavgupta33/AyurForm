from __future__ import annotations

from fastapi.testclient import TestClient

import auth_api


def _enable_dev(monkeypatch):
    monkeypatch.setenv("AYURSUTRA_ENV", "development")
    monkeypatch.setenv("AYURSUTRA_ENABLE_DEV_COOKIE_TEST", "1")
    monkeypatch.setenv("AYURSUTRA_DEV_COOKIE_SECURE", "0")


def test_health():
    response = TestClient(auth_api.app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "ayursutra-local-api"}


def test_cookie_round_trip_and_clear(monkeypatch):
    _enable_dev(monkeypatch)
    client = TestClient(auth_api.app, base_url="http://localhost:8000", client=("127.0.0.1", 50000))
    set_response = client.post("/auth/dev-cookie-test", headers={"Origin": "http://localhost:8501"})
    assert set_response.status_code == 200
    assert set_response.json()["reload_required"] is True
    set_cookie = set_response.headers["set-cookie"].lower()
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    assert "path=/" in set_cookie
    assert "secure" not in set_cookie
    assert "domain=" not in set_cookie
    assert client.get("/auth/dev-cookie-test").json() == {"cookie_received": True}

    clear_response = client.post("/auth/dev-cookie-test/clear")
    assert clear_response.status_code == 200
    assert "max-age=0" in clear_response.headers["set-cookie"].lower()
    assert client.get("/auth/dev-cookie-test").json() == {"cookie_received": False}


def test_dev_endpoints_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AYURSUTRA_ENV", raising=False)
    monkeypatch.delenv("AYURSUTRA_ENABLE_DEV_COOKIE_TEST", raising=False)
    monkeypatch.delenv("AYURSUTRA_DEV_COOKIE_SECURE", raising=False)
    response = TestClient(auth_api.app).post("/auth/dev-cookie-test")
    assert response.status_code == 404


def test_cors_is_exact_and_supports_credentials():
    client = TestClient(auth_api.app)
    allowed = client.options(
        "/auth/dev-cookie-test",
        headers={
            "Origin": "http://localhost:8501",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:8501"
    assert allowed.headers["access-control-allow-credentials"] == "true"

    rejected = client.options(
        "/auth/dev-cookie-test",
        headers={
            "Origin": "http://127.0.0.1:8501",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in rejected.headers
