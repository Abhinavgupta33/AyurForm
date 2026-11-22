"""Small structured AyurForm repository with explicit provenance fields.

Uses DATABASE_URL when it is a SQLite URL; PostgreSQL integration can be
added behind this same interface without changing page/API contracts.
"""
from __future__ import annotations
import os, sqlite3
from pathlib import Path
from config import ROOT_DIR, DATABASE_URL, AYURFORM_DB_FALLBACK
from ayurform_sqlalchemy import session_factory, make_engine

DB_PATH = Path(os.getenv("AYURFORM_DB_PATH", ROOT_DIR / "ayurform_dev.db"))

def backend_name() -> str:
    if DATABASE_URL.startswith(("postgresql://", "postgresql+psycopg://")):
        return "postgresql"
    if AYURFORM_DB_FALLBACK or not DATABASE_URL:
        return "sqlite_development"
    return "unsupported"

def db_health() -> dict:
    if backend_name() == "postgresql":
        try:
            with make_engine().connect() as conn:
                conn.exec_driver_sql("SELECT 1")
            return {"backend":"postgresql", "connected":True}
        except Exception as exc:
            return {"backend":"postgresql", "connected":False, "error":type(exc).__name__}
    if backend_name() == "sqlite_development":
        try:
            with connect() as db: db.execute("SELECT 1")
            return {"backend":"sqlite_development", "connected":True}
        except Exception as exc: return {"backend":"sqlite_development", "connected":False, "error":type(exc).__name__}
    return {"backend":backend_name(), "connected":False}

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources(id INTEGER PRIMARY KEY, source_id TEXT UNIQUE NOT NULL, title TEXT NOT NULL, translator TEXT, editor TEXT, publisher TEXT, edition TEXT, publication_year INTEGER, rights_status TEXT NOT NULL, usage_scope TEXT NOT NULL, review_status TEXT NOT NULL, source_sha256 TEXT);
CREATE TABLE IF NOT EXISTS source_passages(id INTEGER PRIMARY KEY, stable_passage_id TEXT UNIQUE NOT NULL, source_id INTEGER NOT NULL REFERENCES sources(id), text TEXT NOT NULL, pdf_page INTEGER, section TEXT, chapter TEXT, verse_reference TEXT, provenance_role TEXT NOT NULL, review_status TEXT NOT NULL, chroma_id TEXT);
CREATE TABLE IF NOT EXISTS dravya(id INTEGER PRIMARY KEY, canonical_name TEXT UNIQUE NOT NULL, sanskrit_name TEXT, botanical_identity TEXT, botanical_verification_status TEXT, review_status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS dravya_synonyms(id INTEGER PRIMARY KEY, dravya_id INTEGER NOT NULL REFERENCES dravya(id), synonym TEXT NOT NULL, language TEXT, source_passage_id INTEGER REFERENCES source_passages(id), UNIQUE(dravya_id,synonym));
CREATE TABLE IF NOT EXISTS dravya_attributes(id INTEGER PRIMARY KEY, dravya_id INTEGER NOT NULL REFERENCES dravya(id), attribute_type TEXT NOT NULL, attribute_value TEXT NOT NULL, source_passage_id INTEGER NOT NULL REFERENCES source_passages(id), provenance_role TEXT NOT NULL, review_status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS formulations(id INTEGER PRIMARY KEY, canonical_name TEXT UNIQUE NOT NULL, sanskrit_name TEXT, preparation_context TEXT, review_status TEXT NOT NULL, source_passage_id INTEGER REFERENCES source_passages(id));
CREATE TABLE IF NOT EXISTS formulation_ingredients(id INTEGER PRIMARY KEY, formulation_id INTEGER NOT NULL REFERENCES formulations(id), dravya_id INTEGER REFERENCES dravya(id), ingredient_name_recorded TEXT NOT NULL, ingredient_role TEXT, source_passage_id INTEGER NOT NULL REFERENCES source_passages(id), review_status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS anupana_relationships(id INTEGER PRIMARY KEY, anupana_term TEXT NOT NULL, dravya_id INTEGER REFERENCES dravya(id), formulation_id INTEGER REFERENCES formulations(id), source_passage_id INTEGER NOT NULL REFERENCES source_passages(id), relationship_context TEXT NOT NULL, provenance_role TEXT NOT NULL, review_status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS expert_reviews(id INTEGER PRIMARY KEY, entity_type TEXT NOT NULL, entity_id INTEGER NOT NULL, status TEXT NOT NULL, review_notes TEXT, reviewed_at TEXT);
"""

def connect():
    db = sqlite3.connect(DB_PATH); db.row_factory = sqlite3.Row; db.execute("PRAGMA foreign_keys=ON"); return db

def init_db():
    if backend_name() == "postgresql":
        raise RuntimeError("PostgreSQL DATABASE_URL is configured; install SQLAlchemy and psycopg before startup.")
    if backend_name() == "unsupported":
        raise RuntimeError("Unsupported DATABASE_URL. Use PostgreSQL or explicitly set AYURFORM_DB_FALLBACK=sqlite.")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db: db.executescript(SCHEMA)

def rows(table: str, search: str = "", limit: int = 50):
    allowed = {"dravya","formulations","anupana_relationships","sources","source_passages"}
    if table not in allowed: raise ValueError("Unsupported table")
    if backend_name() == "postgresql":
        from ayurform_sqlalchemy import Source, SourcePassage, Dravya, Formulation, AnupanaRelationship
        models = {"sources":Source,"source_passages":SourcePassage,"dravya":Dravya,"formulations":Formulation,"anupana_relationships":AnupanaRelationship}
        model = models[table]; column = getattr(model, {"sources":"title","source_passages":"text","dravya":"canonical_name","formulations":"canonical_name","anupana_relationships":"anupana_term"}[table])
        with session_factory()() as session:
            query = session.query(model).filter(model.review_status == "approved").order_by(model.id).limit(limit)
            if table == "dravya":
                from sqlalchemy import func, or_, exists
                from ayurform_sqlalchemy import DravyaSynonym, DravyaAttribute, SourcePassage, Source
                normalized = " ".join((search or "").split()).casefold()
                eligible_evidence = exists().where(
                    DravyaAttribute.dravya_id == Dravya.id,
                    DravyaAttribute.review_status == "approved",
                    DravyaAttribute.provenance_role == "translated_source",
                    SourcePassage.id == DravyaAttribute.source_passage_id,
                    SourcePassage.review_status == "approved",
                    SourcePassage.provenance_role == "translated_source",
                    Source.id == SourcePassage.source_id,
                    Source.review_status == "approved",
                    Source.usage_scope == "production",
                    Source.rights_status.in_(_PUBLIC_RIGHTS),
                )
                if normalized:
                    def normalized_column(value):
                        return func.lower(func.regexp_replace(func.coalesce(value, ""), r"\s+", " ", "g"))
                    pattern = f"%{normalized}%"
                    query = (session.query(model)
                        .outerjoin(DravyaSynonym, DravyaSynonym.dravya_id == model.id)
                        .filter(model.review_status == "approved")
                        .filter(eligible_evidence)
                        .filter(or_(
                            normalized_column(model.canonical_name).like(pattern),
                            normalized_column(model.sanskrit_name).like(pattern),
                            normalized_column(model.botanical_identity).like(pattern),
                            normalized_column(DravyaSynonym.synonym).like(pattern),
                        )).distinct().order_by(model.id).limit(limit))
                else:
                    query = query.filter(eligible_evidence)
                records = query.all()
                results = []
                for item in records:
                    record = {c.name:getattr(item,c.name) for c in model.__table__.columns}
                    record.update(_postgres_public_dravya_details(session, item.id))
                    results.append(record)
                return results
            elif search:
                query = query.filter(column.ilike(f"%{search}%"))
            return [{c.name:getattr(item,c.name) for c in model.__table__.columns} for item in query.all()]
    with connect() as db:
        if table == "dravya":
            normalized = " ".join((search or "").split()).casefold()
            db.create_function("normalize_search", 1, lambda value: " ".join(str(value or "").split()).casefold())
            like = f"%{normalized}%"
            sql = """SELECT d.* FROM dravya d WHERE d.review_status='approved' AND EXISTS (
                     SELECT 1 FROM dravya_attributes a JOIN source_passages p ON p.id=a.source_passage_id
                     JOIN sources src ON src.id=p.source_id WHERE a.dravya_id=d.id
                     AND a.review_status='approved' AND a.provenance_role='translated_source'
                     AND p.review_status='approved' AND p.provenance_role='translated_source'
                     AND src.review_status='approved' AND src.usage_scope='production'
                     AND src.rights_status IN ('verified','licensed','public_domain')) AND (?='' OR
                     normalize_search(d.canonical_name) LIKE ? OR
                     normalize_search(d.sanskrit_name) LIKE ? OR
                     normalize_search(d.botanical_identity) LIKE ? OR EXISTS (
                       SELECT 1 FROM dravya_synonyms s WHERE s.dravya_id=d.id
                       AND normalize_search(s.synonym) LIKE ?)) ORDER BY d.id LIMIT ?"""
            records = [dict(r) for r in db.execute(sql, (normalized, like, like, like, like, limit))]
            for record in records:
                record.update(_sqlite_public_dravya_details(db, record["id"]))
            return records
        col = {"formulations":"canonical_name", "anupana_relationships":"anupana_term", "sources":"title", "source_passages":"text"}[table]
        return [dict(r) for r in db.execute(f"SELECT * FROM {table} WHERE review_status='approved' AND (?='' OR {col} LIKE ?) ORDER BY id LIMIT ?", (search, f"%{search}%", limit))]


_PUBLIC_RIGHTS = ("verified", "licensed", "public_domain")


def _sqlite_public_dravya_details(db, dravya_id: int) -> dict:
    """Return approved synonyms and source-backed, production-cleared attributes."""
    synonyms = [dict(row) for row in db.execute(
        "SELECT synonym,language,source_passage_id FROM dravya_synonyms WHERE dravya_id=? ORDER BY id",
        (dravya_id,),
    )]
    evidence_rows = db.execute("""SELECT a.attribute_type,a.attribute_value,a.provenance_role,
        p.stable_passage_id,p.pdf_page,p.section,p.chapter,p.verse_reference,
        s.title AS source_title,s.translator,s.editor,s.edition,s.publisher,s.publication_year,
        s.rights_status,s.usage_scope
        FROM dravya_attributes a JOIN source_passages p ON p.id=a.source_passage_id
        JOIN sources s ON s.id=p.source_id
        WHERE a.dravya_id=? AND a.review_status='approved' AND p.review_status='approved'
        AND a.provenance_role='translated_source' AND p.provenance_role='translated_source'
        AND s.review_status='approved' AND s.usage_scope='production'
        AND s.rights_status IN ('verified','licensed','public_domain') ORDER BY a.id""", (dravya_id,)).fetchall()
    attributes = []
    for row in evidence_rows:
        item = dict(row)
        attributes.append({
            "attribute_type": item["attribute_type"], "attribute_value": item["attribute_value"],
            "provenance_role": item["provenance_role"],
            "source_reference": {key: item[key] for key in (
                "stable_passage_id","pdf_page","section","chapter","verse_reference",
                "source_title","translator","editor","edition","publisher","publication_year",
                "rights_status","usage_scope")},
        })
    return {"synonyms": synonyms, "attributes": attributes}


def _postgres_public_dravya_details(session, dravya_id: int) -> dict:
    from ayurform_sqlalchemy import DravyaSynonym, DravyaAttribute, SourcePassage, Source
    synonyms = [{"synonym": row.synonym, "language": row.language, "source_passage_id": row.source_passage_id}
                for row in session.query(DravyaSynonym).filter_by(dravya_id=dravya_id).order_by(DravyaSynonym.id).all()]
    evidence = (session.query(DravyaAttribute, SourcePassage, Source)
        .join(SourcePassage, SourcePassage.id == DravyaAttribute.source_passage_id)
        .join(Source, Source.id == SourcePassage.source_id)
        .filter(DravyaAttribute.dravya_id == dravya_id, DravyaAttribute.review_status == "approved",
            DravyaAttribute.provenance_role == "translated_source",
            SourcePassage.review_status == "approved", SourcePassage.provenance_role == "translated_source",
            Source.review_status == "approved",
            Source.usage_scope == "production", Source.rights_status.in_(_PUBLIC_RIGHTS))
        .order_by(DravyaAttribute.id).all())
    attributes = []
    for attribute, passage, source in evidence:
        attributes.append({
            "attribute_type": attribute.attribute_type, "attribute_value": attribute.attribute_value,
            "provenance_role": attribute.provenance_role,
            "source_reference": {
                "stable_passage_id": passage.stable_passage_id, "pdf_page": passage.pdf_page,
                "section": passage.section, "chapter": passage.chapter,
                "verse_reference": passage.verse_reference, "source_title": source.title,
                "translator": source.translator, "editor": source.editor, "edition": source.edition,
                "publisher": source.publisher, "publication_year": source.publication_year,
                "rights_status": source.rights_status, "usage_scope": source.usage_scope,
            },
        })
    return {"synonyms": synonyms, "attributes": attributes}

def write_record(table: str, values: dict, item_id: int | None = None) -> dict:
    if backend_name() != "postgresql":
        raise RuntimeError("Administrative structured writes require PostgreSQL.")
    from ayurform_sqlalchemy import Source, SourcePassage, Dravya, DravyaSynonym, DravyaAttribute, Formulation, FormulationIngredient, AnupanaRelationship, ExpertReview
    models = {"sources":Source,"source_passages":SourcePassage,"dravya":Dravya,"dravya_synonyms":DravyaSynonym,"dravya_attributes":DravyaAttribute,"formulations":Formulation,"formulation_ingredients":FormulationIngredient,"anupana_relationships":AnupanaRelationship,"expert_reviews":ExpertReview}
    model = models.get(table)
    if model is None: raise ValueError("Unsupported entity")
    if table in {"dravya_attributes","formulation_ingredients","anupana_relationships"} and not values.get("source_passage_id"):
        raise ValueError("A source_passage_id is required for scholarly records")
    if table == "anupana_relationships" and not (values.get("dravya_id") or values.get("formulation_id")):
        raise ValueError("Anupana relationships require an explicit Dravya or formulation link")
    allowed = {c.name for c in model.__table__.columns if not c.primary_key and c.name not in {"created_at","updated_at"}}
    clean = {k:v for k,v in values.items() if k in allowed}
    # New scholarly records always enter review; approval is a separate action.
    if not item_id and table != "expert_reviews" and "review_status" in allowed:
        clean["review_status"] = "pending"
    with session_factory()() as session:
        try:
            obj = session.get(model, item_id) if item_id else model()
            if item_id and obj is None: raise LookupError("Record not found")
            for key, value in clean.items(): setattr(obj, key, value)
            session.add(obj); session.commit(); session.refresh(obj)
            return {c.name:getattr(obj,c.name) for c in model.__table__.columns}
        except Exception:
            session.rollback(); raise

def delete_record(table: str, item_id: int) -> None:
    if backend_name() != "postgresql": raise RuntimeError("Administrative structured deletes require PostgreSQL.")
    from ayurform_sqlalchemy import Source, SourcePassage, Dravya, DravyaSynonym, DravyaAttribute, Formulation, FormulationIngredient, AnupanaRelationship, ExpertReview
    model = {"sources":Source,"source_passages":SourcePassage,"dravya":Dravya,"dravya_synonyms":DravyaSynonym,"dravya_attributes":DravyaAttribute,"formulations":Formulation,"formulation_ingredients":FormulationIngredient,"anupana_relationships":AnupanaRelationship,"expert_reviews":ExpertReview}.get(table)
    if model is None: raise ValueError("Unsupported entity")
    with session_factory()() as session:
        obj = session.get(model, item_id)
        if obj is None: raise LookupError("Record not found")
        session.delete(obj); session.commit()

def approve_record(table: str, item_id: int, reviewer_email: str, notes: str = "") -> dict:
    """Approve only records with source-backed evidence; record reviewer audit."""
    if backend_name() != "postgresql":
        with connect() as db:
            row = db.execute(f"SELECT * FROM {table} WHERE id=?", (item_id,)).fetchone()
            if not row: raise LookupError("Record not found")
            if table == "dravya":
                evidence = db.execute("""SELECT 1 FROM dravya_attributes a
                    JOIN source_passages p ON p.id=a.source_passage_id JOIN sources s ON s.id=p.source_id
                    WHERE a.dravya_id=? AND a.review_status='approved' AND a.provenance_role='translated_source'
                    AND p.review_status='approved' AND p.provenance_role='translated_source'
                    AND s.review_status='approved' AND s.usage_scope='production'
                    AND s.rights_status IN ('verified','licensed','public_domain') LIMIT 1""", (item_id,)).fetchone()
                if not evidence: raise ValueError("Dravya requires an approved source-backed attribute before approval")
            db.execute(f"UPDATE {table} SET review_status='approved' WHERE id=?", (item_id,))
            db.execute("INSERT INTO expert_reviews(entity_type,entity_id,status,review_notes,reviewed_at) VALUES(?,?,?,?,datetime('now'))", (table,item_id,"approved",notes))
            return dict(db.execute(f"SELECT * FROM {table} WHERE id=?", (item_id,)).fetchone())
    from ayurform_sqlalchemy import Dravya, DravyaAttribute, SourcePassage, Source, ExpertReview
    models = {"dravya": Dravya}
    model = models.get(table)
    if model is None: raise ValueError("Unsupported approval entity")
    with session_factory()() as session:
        obj = session.get(model, item_id)
        if obj is None: raise LookupError("Record not found")
        if table == "dravya":
            evidence = (session.query(DravyaAttribute).join(SourcePassage, SourcePassage.id == DravyaAttribute.source_passage_id)
                .join(Source, Source.id == SourcePassage.source_id)
                .filter(DravyaAttribute.dravya_id == item_id, DravyaAttribute.review_status == "approved",
                    DravyaAttribute.provenance_role == "translated_source", SourcePassage.review_status == "approved",
                    SourcePassage.provenance_role == "translated_source", Source.review_status == "approved",
                    Source.usage_scope == "production", Source.rights_status.in_(_PUBLIC_RIGHTS)).first())
            if evidence is None: raise ValueError("Dravya requires approved translated-source evidence with cleared production rights")
        obj.review_status = "approved"
        session.add(ExpertReview(entity_type=table, entity_id=item_id, status="approved", review_notes=notes, reviewed_at=__import__('datetime').datetime.utcnow()))
        session.commit(); session.refresh(obj)
        return {c.name:getattr(obj,c.name) for c in model.__table__.columns}

def pending_records(table: str = "dravya") -> list[dict]:
    if table != "dravya": raise ValueError("Unsupported review entity")
    if backend_name() != "postgresql":
        with connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM dravya WHERE review_status IN ('pending','rejected') ORDER BY id")]
    from ayurform_sqlalchemy import Dravya
    with session_factory()() as session:
        return [{c.name:getattr(x,c.name) for c in Dravya.__table__.columns} for x in session.query(Dravya).filter(Dravya.review_status.in_(["pending","rejected"])).order_by(Dravya.id).all()]


def review_detail_data(entity_type: str, item_id: int) -> dict:
    """Administrator-only detail payload with linked evidence and source rights."""
    if entity_type != "dravya":
        raise ValueError("Unsupported review entity")
    if backend_name() != "postgresql":
        with connect() as db:
            row = db.execute("SELECT * FROM dravya WHERE id=?", (item_id,)).fetchone()
            if not row:
                raise LookupError("Record not found")
            attributes = [dict(x) for x in db.execute(
                "SELECT * FROM dravya_attributes WHERE dravya_id=? ORDER BY id", (item_id,))]
            synonyms = [dict(x) for x in db.execute(
                "SELECT * FROM dravya_synonyms WHERE dravya_id=? ORDER BY id", (item_id,))]
            evidence = [dict(x) for x in db.execute("""SELECT a.id AS attribute_id,a.attribute_type,
                a.attribute_value,a.review_status AS attribute_review_status,a.provenance_role AS attribute_provenance,
                p.stable_passage_id,p.text AS passage_text,p.pdf_page,p.section,p.chapter,p.verse_reference,
                p.provenance_role AS passage_provenance,p.review_status AS passage_review_status,
                s.title AS source_title,s.translator,s.editor,s.edition,s.publisher,s.publication_year,
                s.rights_status,s.usage_scope,s.review_status AS source_review_status,s.source_sha256
                FROM dravya_attributes a JOIN source_passages p ON p.id=a.source_passage_id
                JOIN sources s ON s.id=p.source_id WHERE a.dravya_id=? ORDER BY a.id""", (item_id,))]
        return {"record": dict(row), "attributes": attributes, "synonyms": synonyms,
                "evidence": evidence, "history": review_history(entity_type, item_id)}
    from ayurform_sqlalchemy import Dravya, DravyaAttribute, DravyaSynonym, SourcePassage, Source
    with session_factory()() as session:
        record = session.get(Dravya, item_id)
        if record is None:
            raise LookupError("Record not found")
        attributes = session.query(DravyaAttribute).filter_by(dravya_id=item_id).order_by(DravyaAttribute.id).all()
        synonyms = session.query(DravyaSynonym).filter_by(dravya_id=item_id).order_by(DravyaSynonym.id).all()
        evidence_rows = (session.query(DravyaAttribute, SourcePassage, Source)
            .join(SourcePassage, SourcePassage.id == DravyaAttribute.source_passage_id)
            .join(Source, Source.id == SourcePassage.source_id)
            .filter(DravyaAttribute.dravya_id == item_id).order_by(DravyaAttribute.id).all())
        evidence = []
        for attribute, passage, source in evidence_rows:
            evidence.append({
                "attribute_id": attribute.id, "attribute_type": attribute.attribute_type,
                "attribute_value": attribute.attribute_value,
                "attribute_review_status": attribute.review_status,
                "attribute_provenance": attribute.provenance_role,
                "stable_passage_id": passage.stable_passage_id, "passage_text": passage.text,
                "pdf_page": passage.pdf_page, "section": passage.section, "chapter": passage.chapter,
                "verse_reference": passage.verse_reference, "passage_provenance": passage.provenance_role,
                "passage_review_status": passage.review_status, "source_title": source.title,
                "translator": source.translator, "editor": source.editor, "edition": source.edition,
                "publisher": source.publisher, "publication_year": source.publication_year,
                "rights_status": source.rights_status, "usage_scope": source.usage_scope,
                "source_review_status": source.review_status, "source_sha256": source.source_sha256,
            })
        return {
            "record": {c.name: getattr(record, c.name) for c in Dravya.__table__.columns},
            "attributes": [{c.name: getattr(x, c.name) for c in DravyaAttribute.__table__.columns} for x in attributes],
            "synonyms": [{c.name: getattr(x, c.name) for c in DravyaSynonym.__table__.columns} for x in synonyms],
            "evidence": evidence,
            "history": review_history(entity_type, item_id),
        }


def review_history(entity_type: str, entity_id: int) -> list[dict]:
    if backend_name() != "postgresql":
        with connect() as db: return [dict(r) for r in db.execute("SELECT * FROM expert_reviews WHERE entity_type=? AND entity_id=? ORDER BY id DESC", (entity_type, entity_id))]
    from ayurform_sqlalchemy import ExpertReview
    with session_factory()() as session:
        return [{c.name:getattr(x,c.name) for c in ExpertReview.__table__.columns} for x in session.query(ExpertReview).filter_by(entity_type=entity_type, entity_id=entity_id).order_by(ExpertReview.id.desc()).all()]

if backend_name() == "sqlite_development":
    init_db()
