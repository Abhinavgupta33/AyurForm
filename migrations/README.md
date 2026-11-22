# AyurForm structured-data migrations

The production structured store is PostgreSQL and is selected with `DATABASE_URL`.
The current repository environment does not include SQLAlchemy/Alembic/psycopg;
install requirements before running migrations. SQLite is available only with the
explicit development fallback `AYURFORM_DB_FALLBACK=sqlite`.

Planned first migration creates the nine AyurForm tables defined in `ayurform_store.py`.
