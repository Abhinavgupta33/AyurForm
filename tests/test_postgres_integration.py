"""Real PostgreSQL integration tests.

These tests are intentionally skipped unless AYURFORM_TEST_DATABASE_URL points
to a disposable PostgreSQL database. They never invent credentials or records.
"""
import os
from datetime import datetime
import pytest

TEST_URL = os.getenv("AYURFORM_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_URL, reason="AYURFORM_TEST_DATABASE_URL is not configured")

@pytest.fixture()
def postgres(monkeypatch):
    import config, ayurform_store as store, ayurform_sqlalchemy as models
    from sqlalchemy import text
    engine = models.make_engine(TEST_URL)
    models.Base.metadata.drop_all(engine)
    models.Base.metadata.create_all(engine)
    monkeypatch.setattr(config, "DATABASE_URL", TEST_URL)
    monkeypatch.setattr(models, "DATABASE_URL", TEST_URL)
    monkeypatch.setattr(store, "DATABASE_URL", TEST_URL)
    yield engine, store
    models.Base.metadata.drop_all(engine)
    engine.dispose()

def test_postgres_dravya_evidence_review_and_public_visibility(postgres):
    engine, store = postgres
    with engine.begin() as db:
        source = db.execute(__import__('sqlalchemy').text("INSERT INTO sources(source_id,title,rights_status,usage_scope,review_status) VALUES ('it-source','Integration source','licensed','production','approved') RETURNING id")).scalar_one()
        passage = db.execute(__import__('sqlalchemy').text("INSERT INTO source_passages(stable_passage_id,source_id,text,provenance_role,review_status) VALUES ('it-passage',:source,'Verified integration evidence','translated_source','approved') RETURNING id"), {"source": source}).scalar_one()
        dravya = db.execute(__import__('sqlalchemy').text("INSERT INTO dravya(canonical_name,sanskrit_name,botanical_identity,review_status) VALUES ('Integration Dravya','Sanskrit name','Withania somnifera','pending') RETURNING id")).scalar_one()
        db.execute(__import__('sqlalchemy').text("INSERT INTO dravya_synonyms(dravya_id,synonym,language) VALUES (:d,'Integration synonym','English')"), {"d":dravya})
        db.execute(__import__('sqlalchemy').text("INSERT INTO dravya_attributes(dravya_id,attribute_type,attribute_value,source_passage_id,provenance_role,review_status) VALUES (:d,'Rasa','documented',:p,'translated_source','approved')"), {"d":dravya,"p":passage})
    result = store.approve_record("dravya", dravya, "reviewer@example.org", "Evidence checked")
    assert result["review_status"] == "approved"
    assert store.rows("dravya", "Integration synonym", 10)[0]["canonical_name"] == "Integration Dravya"
    assert store.rows("dravya", "  WITHANIA   SOMNIFERA ", 10)[0]["canonical_name"] == "Integration Dravya"
    history = store.review_history("dravya", dravya)
    assert history[0]["status"] == "approved"
    assert history[0]["reviewed_at"] is not None

def test_postgres_approval_without_evidence_is_atomic(postgres):
    engine, store = postgres
    with engine.begin() as db:
        dravya = db.execute(__import__('sqlalchemy').text("INSERT INTO dravya(canonical_name,review_status) VALUES ('No Evidence','pending') RETURNING id")).scalar_one()
    with pytest.raises(ValueError): store.approve_record("dravya", dravya, "reviewer@example.org")
    with engine.connect() as db:
        assert db.execute(__import__('sqlalchemy').text("SELECT review_status FROM dravya WHERE id=:id"), {"id":dravya}).scalar_one() == "pending"
