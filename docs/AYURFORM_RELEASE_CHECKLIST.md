# AyurForm release checklist

- [x] Existing authentication and SQLite auth database preserved.
- [x] PostgreSQL SQLAlchemy models and Alembic migration present.
- [x] Explicit SQLite development fallback.
- [x] Provenance-gated semantic retrieval.
- [x] Typed research intent classification and abstention service.
- [x] Citation validation remains delegated to the existing validator.
- [x] Admin write boundary requires auth cookie and `AYURFORM_ADMIN_EMAILS`.
- [x] Docker Compose defines PostgreSQL, API and Streamlit services.
- [ ] Live PostgreSQL migration verification with configured credentials.
- [ ] Docker build/startup verification (Docker unavailable in this environment).
- [ ] Rights-cleared scholarly records and expert approval workflow data.
- [ ] Full PostgreSQL CRUD integration tests against a live database.
- [ ] Remote Ollama/AyurParam endpoint verification.

The release is not claimed production-ready until the unchecked infrastructure and data-rights items are completed.
