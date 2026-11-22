# AyurForm AI MVP implementation

## Implemented

- AyurForm branding and navigation entries for Dravya, Formulation, Anupana, Research Assistant and Classical Sources.
- Structured development repository with source, passage, Dravya, formulation, Anupana and expert-review tables.
- Empty-state-safe explorer pages that do not present the unverified Charaka development corpus as approved scholarship.
- Minimal FastAPI `/api/health`, entity listing and passage/source routes in `ayurform_api.py`.
- Dockerfile and PostgreSQL docker-compose service definition.
- Existing authentication, Ollama/AyurParam adapter, BGE/ChromaDB and provenance controls preserved.

## Files added/modified

- `ayurform_store.py`
- `ayurform_api.py`
- `frontend/pages/ayurform_pages.py`
- `app.py`
- `frontend/navigation.py`
- `Dockerfile`
- `docker-compose.yml`

## Local commands

```powershell
cd D:\Project\ayursutra-ai
.\.venv\Scripts\python.exe -m uvicorn auth_api:app --host 127.0.0.1 --port 8000
streamlit run app.py --server.port 8501
```

The structured store uses PostgreSQL when `DATABASE_URL` is set. SQLite remains available only through the explicit `AYURFORM_DB_FALLBACK=sqlite` development switch. Docker Compose now defines separate API and Streamlit services with PostgreSQL internal hostname routing. No scholarly records are loaded by this MVP slice.

## Verification

Existing full suite: **81 passed**. No live cloud deployment or production AyurParam service is claimed. The local Ollama dependency remains external and must be started separately.

## Remaining implementation work

- Complete PostgreSQL repository and Alembic migrations using `DATABASE_URL`.
- Add authenticated/admin CRUD and review routes.
- Add structured hybrid research orchestration combining PostgreSQL and ChromaDB.
- Add approved rights-cleared scholarly records and expert review workflow.
- Replace placeholder explorer JSON rendering with polished detail views and citation navigation.
