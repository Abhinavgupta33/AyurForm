"""Local FastAPI service for AyurSutra authentication and the dev cookie probe.

Run locally with: python -m uvicorn auth_api:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import ipaddress
import os
import time
from dotenv import load_dotenv
load_dotenv()
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from auth_service import ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE, AuthError, AuthService, AuthSettings
from deployment_validate import validate_or_raise
from utils.diagnostics import configure_file_logging

validate_or_raise()
configure_file_logging()

COOKIE_NAME = "ayursutra_dev_cookie_marker"


class SignupRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class ProfileRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)


class RateLimiter:
    """Local-process limiter. Use shared storage before deploying multiple workers."""
    def __init__(self, limit: int = 5, window_seconds: int = 60):
        self.limit, self.window_seconds = limit, window_seconds
        self.events: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> bool:
        now = time.monotonic()
        bucket = self.events[key]
        while bucket and bucket[0] <= now - self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return False
        bucket.append(now)
        return True


def _dev_cookie_test_enabled() -> bool:
    return (
        os.getenv("AYURSUTRA_ENV", "").casefold() == "development"
        and os.getenv("AYURSUTRA_ENABLE_DEV_COOKIE_TEST") == "1"
        and os.getenv("AYURSUTRA_DEV_COOKIE_SECURE") == "0"
    )


def _require_local_dev(request: Request) -> None:
    if not _dev_cookie_test_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    host = request.client.host if request.client else ""
    try:
        if not ipaddress.ip_address(host).is_loopback:
            raise HTTPException(status_code=404, detail="Not found")
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found") from None


def _error(error: AuthError) -> JSONResponse:
    return JSONResponse({"detail": {"code": error.code, "message": error.message}}, status_code=error.status_code, headers={"Cache-Control": "no-store"})


def _set_auth_cookies(response: Response, access: str, refresh: str, csrf: str, settings: AuthSettings) -> None:
    shared = {"path": "/", "secure": settings.cookie_secure, "samesite": "lax"}
    response.set_cookie(ACCESS_COOKIE, access, httponly=True, max_age=15 * 60, **shared)
    response.set_cookie(REFRESH_COOKIE, refresh, httponly=True, max_age=7 * 24 * 60 * 60, **shared)
    # CSRF cookie is deliberately readable by the browser so it can be echoed in X-CSRF-Token.
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, max_age=7 * 24 * 60 * 60, **shared)


def _clear_auth_cookies(response: Response, settings: AuthSettings) -> None:
    shared = {"path": "/", "secure": settings.cookie_secure, "samesite": "lax"}
    for name in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, **shared)


def create_app(settings: AuthSettings | None = None, *, migrate_database: bool = True) -> FastAPI:
    auth_settings = settings or AuthSettings.from_env()
    service = AuthService(auth_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if auth_settings.jwt_secret:
            service.initialize(create_backup=migrate_database)
        yield

    api = FastAPI(title="AyurSutra Local API", docs_url=None, redoc_url=None, lifespan=lifespan)
    api.state.auth_service, api.state.auth_settings = service, auth_settings
    api.state.rate_limiter = RateLimiter()
    api.add_middleware(
        CORSMiddleware,
        allow_origins=[auth_settings.allowed_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

    @api.exception_handler(AuthError)
    async def auth_error_handler(_: Request, error: AuthError):
        return _error(error)

    @api.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, __: RequestValidationError):
        return JSONResponse({"detail": {"code": "invalid_input", "message": "Check the submitted fields."}}, status_code=422, headers={"Cache-Control": "no-store"})

    def current_service(request: Request) -> AuthService:
        return request.app.state.auth_service

    def _origin_allowed(request: Request) -> bool:
        origin = request.headers.get("origin")
        return bool(origin and origin == auth_settings.allowed_origin)

    def _csrf(request: Request) -> str | None:
        return request.headers.get("x-csrf-token") if _origin_allowed(request) else None

    def _rate_limit(request: Request, route: str, email: str) -> None:
        ip = request.client.host if request.client else "unknown"
        limiter = request.app.state.rate_limiter
        if not limiter.check(f"{route}:{ip}") or not limiter.check(f"{route}:{ip}:{email.casefold().strip()}"):
            raise AuthError("rate_limited", "Try again later.", 429)

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "ayursutra-local-api"}

    @api.post("/auth/signup")
    def signup(payload: SignupRequest, request: Request, response: Response, service: AuthService = Depends(current_service)):
        _rate_limit(request, "signup", payload.email)
        user, access, refresh, csrf = service.signup(payload.full_name, payload.email, payload.password)
        _set_auth_cookies(response, access, refresh, csrf, auth_settings)
        response.headers["Cache-Control"] = "no-store"
        return {"user": user}

    @api.post("/auth/login")
    def login(payload: LoginRequest, request: Request, response: Response, service: AuthService = Depends(current_service)):
        _rate_limit(request, "login", payload.email)
        user, access, refresh, csrf = service.login(payload.email, payload.password)
        _set_auth_cookies(response, access, refresh, csrf, auth_settings)
        response.headers["Cache-Control"] = "no-store"
        return {"user": user}

    @api.post("/auth/refresh")
    def refresh(request: Request, response: Response, service: AuthService = Depends(current_service)):
        user, access, refresh_value, csrf = service.refresh(request.cookies.get(REFRESH_COOKIE), _csrf(request))
        _set_auth_cookies(response, access, refresh_value, csrf, auth_settings)
        response.headers["Cache-Control"] = "no-store"
        return {"user": user}

    @api.post("/auth/logout", status_code=204)
    def logout(request: Request, response: Response, service: AuthService = Depends(current_service)):
        service.logout(request.cookies.get(REFRESH_COOKIE), _csrf(request))
        _clear_auth_cookies(response, auth_settings)
        response.headers["Cache-Control"] = "no-store"
        response.status_code = 204
        return response

    @api.get("/auth/me")
    def me(request: Request, service: AuthService = Depends(current_service)):
        result = service.principal(request.cookies.get(ACCESS_COOKIE))
        return JSONResponse({"user": {key: value for key, value in result.items() if key != "session_id"}}, headers={"Cache-Control": "no-store"})

    @api.patch("/auth/me")
    def update_me(payload: ProfileRequest, request: Request, service: AuthService = Depends(current_service)):
        user = service.update_profile(request.cookies.get(ACCESS_COOKIE), _csrf(request), payload.full_name)
        return JSONResponse({"user": user}, headers={"Cache-Control": "no-store"})

    @api.post("/auth/dev-cookie-test")
    def set_dev_cookie(request: Request, response: Response) -> dict[str, bool | str]:
        _require_local_dev(request)
        response.set_cookie(COOKIE_NAME, os.urandom(24).hex(), max_age=600, path="/", httponly=True, secure=False, samesite="lax")
        return {"status": "cookie_set", "reload_required": True}

    @api.get("/auth/dev-cookie-test")
    def check_dev_cookie(request: Request) -> dict[str, bool]:
        _require_local_dev(request)
        return {"cookie_received": COOKIE_NAME in request.cookies}

    @api.post("/auth/dev-cookie-test/clear")
    def clear_dev_cookie(request: Request, response: Response) -> dict[str, bool | str]:
        _require_local_dev(request)
        response.delete_cookie(COOKIE_NAME, path="/", httponly=True, secure=False, samesite="lax")
        return {"status": "cookie_cleared", "reload_required": True}

    return api


app = create_app()
