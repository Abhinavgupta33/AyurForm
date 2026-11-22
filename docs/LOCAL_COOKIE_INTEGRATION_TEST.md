# Local FastAPI ↔ Streamlit cookie test

This is a development-only transport test. It does not implement accounts, passwords, JWTs, or authentication. The random marker is harmless and expires after ten minutes.

The same FastAPI process now also contains the authentication backend. Set a strong local signing secret to exercise `/auth/signup`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/me`, and `/auth/me` PATCH. No login UI is included in this milestone.

## Install project dependencies

From the project root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Start FastAPI

Open PowerShell terminal 1 and run:

```powershell
cd D:\Project\ayursutra-ai
$env:AYURSUTRA_ENV = "development"
$env:AYURSUTRA_ENABLE_DEV_COOKIE_TEST = "1"
$env:AYURSUTRA_DEV_COOKIE_SECURE = "0"
$env:AYURSUTRA_AUTH_COOKIE_SECURE = "0"
$authSigningSecret = Read-Host "Enter a local signing secret (32+ characters)"
$env:AYURSUTRA_AUTH_JWT_SECRET = $authSigningSecret
.\.venv\Scripts\python.exe -m uvicorn auth_api:app --host 127.0.0.1 --port 8000
```

The explicit `AYURSUTRA_DEV_COOKIE_SECURE=0` setting permits an insecure cookie only for this local HTTP test. The service binds to loopback, and the cookie endpoints also require a loopback client. Do not set these development flags in a deployed environment.

## Start Streamlit

Open PowerShell terminal 2 and run:

```powershell
cd D:\Project\ayursutra-ai
$env:AYURSUTRA_ENV = "development"
$env:AYURSUTRA_ENABLE_DEV_COOKIE_TEST = "1"
$env:AYURSUTRA_DEV_COOKIE_SECURE = "0"
$env:AYURSUTRA_AUTH_COOKIE_SECURE = "0"
$authSigningSecret = Read-Host "Enter the same local signing secret"
$env:AYURSUTRA_AUTH_JWT_SECRET = $authSigningSecret
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

The usual `streamlit run app.py` command remains available for normal use; the test panel is hidden unless all three development settings above are present in that Streamlit process.

## Run the round trip

1. Open `http://localhost:8501` and select **Settings**.
2. Confirm the initial server-side status says the marker is not detected.
3. Click **Set test cookie**. The browser sends a credentialed request directly to `http://localhost:8000`.
4. The panel reports whether the browser can read the marker through `document.cookie` (it should say no because it is HttpOnly).
5. Click **Check browser request**; FastAPI should report that it received the cookie.
6. Click **Reload this page**. The Streamlit status should now say the marker is detected from the new WebSocket handshake.
7. In browser developer tools, inspect the `ayursutra_dev_cookie_marker` cookie for `HttpOnly`, `SameSite=Lax`, Path `/`, no Domain, and no Secure flag (local HTTP only).
8. Click **Clear test cookie**, then reload. The Streamlit status should return to not detected.

FastAPI health check: `http://localhost:8000/health` should return `{"status":"ok","service":"ayursutra-local-api"}`.

## Stop services

Press `Ctrl+C` in each terminal. Do not terminate unrelated Python processes by name.

## Run focused API tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dev_auth_api.py -q
```

To run the full backend test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_auth_backend.py tests/test_dev_auth_api.py -q
```
