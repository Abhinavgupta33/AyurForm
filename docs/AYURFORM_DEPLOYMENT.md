# AyurForm deployment

## Local development

```powershell
cd D:\Project\ayursutra-ai
$env:AYURFORM_DB_FALLBACK="sqlite"
$env:AYURFORM_API_URL="http://127.0.0.1:8002"
Start-Process powershell -ArgumentList "-NoExit", "-Command", ".\.venv\Scripts\python.exe -m uvicorn auth_api:app --host 127.0.0.1 --port 8000"
.\.venv\Scripts\python.exe -m uvicorn ayurform_api:app --host 127.0.0.1 --port 8002
streamlit run app.py --server.port 8501
```

For PostgreSQL, create a database/user and set:

```powershell
$env:DATABASE_URL="postgresql+psycopg://<user>:<password>@localhost:5432/ayurform"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn ayurform_api:app --host 127.0.0.1 --port 8002
```

## Compose

Install Docker Desktop, then:

```powershell
docker compose up --build
```

The auth API listens on port 8000, the AyurForm API on 8002, and Streamlit on 8501. Inside Compose, services use `auth:8000`, `api:8002`, and `postgres:5432`; `localhost` inside a container is not another service.

Run a local health check with:

```powershell
.\scripts\check-ayurform-health.ps1
```

Production validation can be checked before startup with:

```powershell
.\.venv\Scripts\python.exe deployment_validate.py
```

## External model

Ollama/AyurParam is not included in the image. Configure `OLLAMA_BASE_URL` to a reachable secured endpoint. A local host Ollama process is not automatically reachable from a container using `127.0.0.1`.
