"""SQLite migrations and persistence primitives for the authentication service."""
from __future__ import annotations

import hashlib
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from config import ROOT_DIR

DEFAULT_DB_PATH = ROOT_DIR / "ayursutra_user.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 5000")
    return db


def _columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}


def _backup(path: Path) -> Path:
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_dir / f"{path.stem}.pre_auth_{stamp}{path.suffix}"
    shutil.copy2(path, backup)
    return backup


def migrate(path: Path | str = DEFAULT_DB_PATH, *, create_backup: bool = True) -> int:
    """Apply all migrations atomically and return the schema version.

    An existing application database is copied before its first auth migration.
    Historical analyses and saved references retain their IDs and remain unowned.
    """
    db_path = Path(path)
    existed = db_path.exists()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as db:
        db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        applied = {row["version"] for row in db.execute("SELECT version FROM schema_migrations")}
    if 1 in applied:
        return max(applied)
    if existed and create_backup:
        _backup(db_path)

    with connect(db_path) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            db.execute("CREATE TABLE IF NOT EXISTS analyses(id INTEGER PRIMARY KEY, created_at TEXT, query TEXT, payload TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS saved_refs(id INTEGER PRIMARY KEY, created_at TEXT, passage_id TEXT UNIQUE, reference TEXT, text TEXT, metadata TEXT)")
            db.execute(
                """CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS auth_sessions (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    refresh_token_hash TEXT NOT NULL,
                    csrf_token_hash TEXT NOT NULL,
                    token_family_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_used_at TEXT NOT NULL,
                    revoked_at TEXT,
                    reuse_detected_at TEXT
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS auth_refresh_tokens (
                    token_hash TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES auth_sessions(id) ON DELETE CASCADE,
                    issued_at TEXT NOT NULL,
                    used_at TEXT,
                    revoked_at TEXT
                )"""
            )
            for table in ("analyses", "saved_refs"):
                if "user_id" not in _columns(db, table):
                    db.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
                db.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_user_id ON {table}(user_id)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON auth_sessions(user_id)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_family ON auth_sessions(token_family_id)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_session ON auth_refresh_tokens(session_id)")
            db.execute("INSERT INTO schema_migrations(version, applied_at) VALUES(1, ?)", (utc_now(),))
            db.commit()
        except Exception:
            db.rollback()
            raise
    return 1


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def row_as_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


def values(rows: Iterable[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]
