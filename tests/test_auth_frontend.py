from types import SimpleNamespace

import httpx

from frontend import auth


def test_validate_access_cookie_skips_empty_cookie(monkeypatch):
    called = False

    def fail(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("request should not be made")

    monkeypatch.setattr(auth.httpx, "get", fail)
    assert auth.validate_access_cookie(None).user is None
    assert called is False


def test_validate_access_cookie_returns_user(monkeypatch):
    monkeypatch.setattr(
        auth.httpx,
        "get",
        lambda *args, **kwargs: SimpleNamespace(status_code=200, json=lambda: {"user": {"id": 7}}),
    )
    result = auth.validate_access_cookie("opaque", api_url="http://auth.test")
    assert result.user == {"id": 7}


def test_validate_access_cookie_handles_invalid_or_unavailable_service(monkeypatch):
    monkeypatch.setattr(
        auth.httpx,
        "get",
        lambda *args, **kwargs: SimpleNamespace(status_code=401, json=lambda: {}),
    )
    assert auth.validate_access_cookie("opaque").user is None

    def unavailable(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(auth.httpx, "get", unavailable)
    result = auth.validate_access_cookie("opaque")
    assert result.user is None
    assert result.unavailable is True
