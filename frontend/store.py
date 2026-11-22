"""SQLite persistence for analysis history and saved passage references."""
import json
import sqlite3
from datetime import datetime, timezone
from config import ROOT_DIR

DB_PATH=ROOT_DIR/'ayursutra_user.db'

def connect():
    db=sqlite3.connect(DB_PATH);db.row_factory=sqlite3.Row
    db.execute('CREATE TABLE IF NOT EXISTS analyses(id INTEGER PRIMARY KEY, created_at TEXT, query TEXT, payload TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS saved_refs(id INTEGER PRIMARY KEY, created_at TEXT, passage_id TEXT UNIQUE, reference TEXT, text TEXT, metadata TEXT)')
    db.commit();return db

def add_analysis(payload):
    with connect() as db: db.execute('INSERT INTO analyses(created_at,query,payload) VALUES(?,?,?)',(datetime.now(timezone.utc).isoformat(),payload['user_query'],json.dumps(payload,ensure_ascii=False)))

def analyses(search=''):
    with connect() as db:return [dict(r) for r in db.execute('SELECT * FROM analyses WHERE query LIKE ? ORDER BY id DESC LIMIT 100',(f'%{search}%',))]

def analysis_count():
    with connect() as db:return db.execute('SELECT COUNT(*) FROM analyses').fetchone()[0]

def delete_analysis(item_id):
    with connect() as db:db.execute('DELETE FROM analyses WHERE id=?',(item_id,))

def save_passage(p):
    with connect() as db:db.execute('INSERT OR IGNORE INTO saved_refs(created_at,passage_id,reference,text,metadata) VALUES(?,?,?,?,?)',(datetime.now(timezone.utc).isoformat(),p['id'],p['reference'],p['text'],json.dumps(p.get('metadata',{}),ensure_ascii=False)))

def saved(search=''):
    with connect() as db:return [dict(r) for r in db.execute('SELECT * FROM saved_refs WHERE reference LIKE ? OR text LIKE ? ORDER BY id DESC',(f'%{search}%',f'%{search}%'))]

def delete_saved(item_id):
    with connect() as db:db.execute('DELETE FROM saved_refs WHERE id=?',(item_id,))

def clear_user_data():
    with connect() as db:db.execute('DELETE FROM analyses');db.execute('DELETE FROM saved_refs')
