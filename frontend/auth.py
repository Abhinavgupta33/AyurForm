"""Server-side validation of Streamlit's initial browser-cookie snapshot."""
from __future__ import annotations

import os
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv
load_dotenv()
import streamlit as st

from auth_service import ACCESS_COOKIE

AUTH_API_URL = os.getenv("AYURSUTRA_AUTH_API_URL", "http://localhost:8000").rstrip("/")


@dataclass(frozen=True)
class SessionCheck:
    user: dict | None
    unavailable: bool = False


def validate_access_cookie(access_cookie: str | None, *, api_url: str = AUTH_API_URL) -> SessionCheck:
    """Ask FastAPI to verify a captured HttpOnly access cookie without storing it."""
    if not access_cookie:
        return SessionCheck(user=None)
    try:
        response = httpx.get(
            f"{api_url}/auth/me",
            headers={"Cookie": f"{ACCESS_COOKIE}={access_cookie}"},
            timeout=3.0,
        )
    except httpx.HTTPError:
        return SessionCheck(user=None, unavailable=True)
    if response.status_code != 200:
        return SessionCheck(user=None)
    try:
        user = response.json().get("user")
    except ValueError:
        return SessionCheck(user=None, unavailable=True)
    return SessionCheck(user=user if isinstance(user, dict) else None)


def current_authenticated_user() -> SessionCheck:
    """Validate only the WebSocket handshake cookie supplied by Streamlit."""
    try:
        access_cookie = st.context.cookies.get(ACCESS_COOKIE)
    except Exception:
        access_cookie = None
    return validate_access_cookie(access_cookie)
