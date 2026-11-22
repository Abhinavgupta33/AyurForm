from pathlib import Path
import pytest
import ayurform_store as store

def test_newly_created_scholarly_record_is_forced_to_pending(monkeypatch):
    monkeypatch.setattr(store, "backend_name", lambda: "postgresql")
    class Session:
        def __init__(self): self.item = None
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def add(self, item): self.item = item
        def commit(self): pass
        def refresh(self, item): pass
        def rollback(self): pass
    session = Session()
    monkeypatch.setattr(store, "session_factory", lambda: lambda: session)
    created = store.write_record("dravya", {"canonical_name":"Imported only for test", "review_status":"approved"})
    assert created["review_status"] == "pending"

def test_dravya_cannot_be_approved_without_approved_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", Path(tmp_path) / "db.sqlite")
    store.init_db()
    with store.connect() as db:
        db.execute("INSERT INTO dravya(canonical_name,review_status) VALUES(?,?)", ("Pending", "pending"))
    with pytest.raises(ValueError, match="source-backed"):
        store.approve_record("dravya", 1, "admin@example.org")

def test_approved_dravya_requires_approved_passage_and_attribute(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", Path(tmp_path) / "db.sqlite")
    store.init_db()
    with store.connect() as db:
        db.execute("INSERT INTO sources(source_id,title,rights_status,usage_scope,review_status) VALUES(?,?,?,?,?)", ("s1","Source","licensed","production","approved"))
        db.execute("INSERT INTO source_passages(stable_passage_id,source_id,text,provenance_role,review_status) VALUES(?,?,?,?,?)", ("p1",1,"evidence","translated_source","approved"))
        db.execute("INSERT INTO dravya(canonical_name,review_status) VALUES(?,?)", ("Pending", "pending"))
        db.execute("INSERT INTO dravya_attributes(dravya_id,attribute_type,attribute_value,source_passage_id,provenance_role,review_status) VALUES(?,?,?,?,?,?)", (1,"Rasa","bitter",1,"translated_source","approved"))
    result = store.approve_record("dravya", 1, "admin@example.org")
    assert result["review_status"] == "approved"


@pytest.mark.parametrize("role,rights,scope", [
    ("editor_note", "licensed", "production"),
    ("unknown", "licensed", "production"),
    ("translated_source", "pending", "development_only"),
])
def test_dravya_approval_rejects_ineligible_provenance_or_rights(tmp_path, monkeypatch, role, rights, scope):
    monkeypatch.setattr(store, "DB_PATH", Path(tmp_path) / "db.sqlite")
    store.init_db()
    with store.connect() as db:
        db.execute("INSERT INTO sources(source_id,title,rights_status,usage_scope,review_status) VALUES(?,?,?,?,?)", ("s1","Source",rights,scope,"approved"))
        db.execute("INSERT INTO source_passages(stable_passage_id,source_id,text,provenance_role,review_status) VALUES(?,?,?,?,?)", ("p1",1,"evidence",role,"approved"))
        db.execute("INSERT INTO dravya(canonical_name,review_status) VALUES(?,?)", ("Pending", "pending"))
        db.execute("INSERT INTO dravya_attributes(dravya_id,attribute_type,attribute_value,source_passage_id,provenance_role,review_status) VALUES(?,?,?,?,?,?)", (1,"Rasa","documented",1,role,"approved"))
    with pytest.raises(ValueError, match="source-backed"):
        store.approve_record("dravya", 1, "admin@example.org")
    with store.connect() as db:
        assert db.execute("SELECT review_status FROM dravya WHERE id=1").fetchone()[0] == "pending"
