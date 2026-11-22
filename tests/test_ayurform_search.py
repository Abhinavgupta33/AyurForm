from pathlib import Path

import ayurform_store as store


def _seed_search_records(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", Path(tmp_path) / "ayurform.db")
    store.init_db()
    with store.connect() as db:
        db.execute(
            "INSERT INTO dravya(canonical_name,sanskrit_name,botanical_identity,review_status) VALUES(?,?,?,?)",
            ("Ashwagandha", "Aśvagandhā", "Withania somnifera", "approved"),
        )
        db.execute(
            "INSERT INTO dravya_synonyms(dravya_id,synonym,language) VALUES(?,?,?)",
            (1, "Winter cherry", "English"),
        )
        db.execute(
            "INSERT INTO dravya_synonyms(dravya_id,synonym,language) VALUES(?,?,?)",
            (1, "Withania somnifera", "botanical"),
        )
        db.execute(
            "INSERT INTO sources(source_id,title,rights_status,usage_scope,review_status) VALUES(?,?,?,?,?)",
            ("search-source", "Reviewed search source", "licensed", "production", "approved"),
        )
        db.execute(
            "INSERT INTO source_passages(stable_passage_id,source_id,text,provenance_role,review_status) VALUES(?,?,?,?,?)",
            ("search-passage", 1, "Reviewed source passage", "translated_source", "approved"),
        )
        db.execute(
            "INSERT INTO dravya_attributes(dravya_id,attribute_type,attribute_value,source_passage_id,provenance_role,review_status) VALUES(?,?,?,?,?,?)",
            (1, "Karma", "documented in source", 1, "translated_source", "approved"),
        )
        db.execute("INSERT INTO dravya(canonical_name,review_status) VALUES(?,?)", ("Hidden pending record", "pending"))
        db.execute("INSERT INTO dravya(canonical_name,review_status) VALUES(?,?)", ("Hidden rejected record", "rejected"))
    return store.DB_PATH


def test_dravya_search_matches_canonical_sanskrit_synonym_and_botanical(tmp_path, monkeypatch):
    _seed_search_records(tmp_path, monkeypatch)
    for query in ("Ashwagandha", "Aśvagandhā", "Winter cherry", "Withania somnifera"):
        assert [row["canonical_name"] for row in store.rows("dravya", query, 50)] == ["Ashwagandha"]


def test_dravya_search_is_case_insensitive_partial_and_normalizes_whitespace(tmp_path, monkeypatch):
    _seed_search_records(tmp_path, monkeypatch)
    for query in ("ashwa", "WITHANIA", "  winter   CHERRY  ", " aśva  "):
        assert [row["canonical_name"] for row in store.rows("dravya", query, 50)] == ["Ashwagandha"]


def test_pending_and_rejected_records_never_appear_in_public_search(tmp_path, monkeypatch):
    _seed_search_records(tmp_path, monkeypatch)
    assert store.rows("dravya", "Hidden", 50) == []
    assert all(row["review_status"] == "approved" for row in store.rows("dravya", "", 50))


def test_approved_record_without_eligible_translated_rights_cleared_evidence_is_hidden(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", Path(tmp_path) / "ayurform.db")
    store.init_db()
    with store.connect() as db:
        db.execute("INSERT INTO dravya(canonical_name,review_status) VALUES(?,?)", ("Unsubstantiated", "approved"))
    assert store.rows("dravya", "Unsubstantiated", 50) == []


def test_approved_search_returns_only_rights_cleared_source_backed_attributes(tmp_path, monkeypatch):
    _seed_search_records(tmp_path, monkeypatch)
    with store.connect() as db:
        clear_source_id = db.execute(
            "INSERT INTO sources(source_id,title,translator,edition,rights_status,usage_scope,review_status) VALUES(?,?,?,?,?,?,?)",
            ("clear-source", "Cleared reference", "Verified translator", "Second edition", "licensed", "production", "approved"),
        ).lastrowid
        passage_id = db.execute(
            "INSERT INTO source_passages(stable_passage_id,source_id,text,pdf_page,chapter,verse_reference,provenance_role,review_status) VALUES(?,?,?,?,?,?,?,?)",
            ("passage-cleared", clear_source_id, "Source-backed attribute text", 42, "Sutra 3", "Su3#12", "translated_source", "approved"),
        ).lastrowid
        db.execute(
            "INSERT INTO dravya_attributes(dravya_id,attribute_type,attribute_value,source_passage_id,provenance_role,review_status) VALUES(?,?,?,?,?,?)",
            (1, "Rasa", "recorded value", passage_id, "translated_source", "approved"),
        )
        pending_source_id = db.execute(
            "INSERT INTO sources(source_id,title,rights_status,usage_scope,review_status) VALUES(?,?,?,?,?)",
            ("pending-source", "Rights pending source", "pending", "development_only", "pending"),
        ).lastrowid
        db.execute(
            "INSERT INTO source_passages(stable_passage_id,source_id,text,pdf_page,provenance_role,review_status) VALUES(?,?,?,?,?,?)",
            ("passage-pending", pending_source_id, "Pending content", 99, "translated_source", "approved"),
        )
        db.execute(
            "INSERT INTO dravya_attributes(dravya_id,attribute_type,attribute_value,source_passage_id,provenance_role,review_status) VALUES(?,?,?,?,?,?)",
            (1, "Karma", "must stay hidden", db.execute("SELECT id FROM source_passages WHERE stable_passage_id='passage-pending'").fetchone()[0], "translated_source", "approved"),
        )
    result = store.rows("dravya", "Withania", 10)[0]
    rasa = next(attribute for attribute in result["attributes"] if attribute["attribute_type"] == "Rasa")
    assert rasa == {
        "attribute_type": "Rasa",
        "attribute_value": "recorded value",
        "provenance_role": "translated_source",
        "source_reference": {
            "stable_passage_id": "passage-cleared", "pdf_page": 42,
            "section": None, "chapter": "Sutra 3", "verse_reference": "Su3#12",
            "source_title": "Cleared reference", "translator": "Verified translator",
            "editor": None, "edition": "Second edition", "publisher": None,
            "publication_year": None, "rights_status": "licensed", "usage_scope": "production",
        },
    }
    assert not any(attribute["attribute_value"] == "must stay hidden" for attribute in result["attributes"])


def test_admin_review_detail_includes_passage_page_provenance_and_license(tmp_path, monkeypatch):
    _seed_search_records(tmp_path, monkeypatch)
    with store.connect() as db:
        source_id = db.execute(
            "INSERT INTO sources(source_id,title,translator,edition,rights_status,usage_scope,review_status) VALUES(?,?,?,?,?,?,?)",
            ("review-source", "Reviewer source", "Translator", "Edition", "pending", "development_only", "pending"),
        ).lastrowid
        passage_id = db.execute(
            "INSERT INTO source_passages(stable_passage_id,source_id,text,pdf_page,chapter,provenance_role,review_status) VALUES(?,?,?,?,?,?,?)",
            ("review-passage", source_id, "Full passage text for reviewer", 17, "Sutra 2", "editor_note", "pending"),
        ).lastrowid
        db.execute(
            "INSERT INTO dravya_attributes(dravya_id,attribute_type,attribute_value,source_passage_id,provenance_role,review_status) VALUES(?,?,?,?,?,?)",
            (1, "Guna", "pending value", passage_id, "editor_note", "pending"),
        )
    detail = store.review_detail_data("dravya", 1)
    evidence = next(row for row in detail["evidence"] if row["attribute_type"] == "Guna")
    assert evidence["passage_text"] == "Full passage text for reviewer"
    assert evidence["pdf_page"] == 17
    assert evidence["passage_provenance"] == "editor_note"
    assert evidence["rights_status"] == "pending"
    assert evidence["usage_scope"] == "development_only"


def test_empty_dravya_search_is_safe(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", Path(tmp_path) / "empty.db")
    store.init_db()
    assert store.rows("dravya", "Ashwagandha", 50) == []


def test_public_api_search_returns_only_approved_records(tmp_path, monkeypatch):
    _seed_search_records(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from ayurform_api import app
    response = TestClient(app).get("/api/dravya", params={"search": "withania"})
    assert response.status_code == 200
    assert [item["canonical_name"] for item in response.json()["items"]] == ["Ashwagandha"]
