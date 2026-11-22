import os
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, Query, HTTPException, Request
from pydantic import BaseModel, Field
from ayurform_store import backend_name, db_health, init_db, rows, connect, write_record, delete_record, approve_record, pending_records, review_history, review_detail_data
from deployment_validate import validate_or_raise

validate_or_raise()
app = FastAPI(title="AyurForm AI API")
if backend_name() == "sqlite_development": init_db()

@app.get("/api/health")
def health(): return {"status":"ok", "service":"ayurform", "database":db_health()}

def require_admin(request: Request):
    # Admin writes require a validated auth cookie and an explicit email allowlist.
    from auth_service import ACCESS_COOKIE
    token = request.cookies.get(ACCESS_COOKIE)
    if not token: raise HTTPException(401, "Authentication required")
    allowed = {x.strip().casefold() for x in os.getenv("AYURFORM_ADMIN_EMAILS", "").split(",") if x.strip()}
    if not allowed: raise HTTPException(403, "Administrative access is not configured")
    try:
        from auth_service import AuthService, AuthSettings
        user = AuthService(AuthSettings.from_env()).principal(token)
        if user.get("email", "").casefold() not in allowed: raise HTTPException(403, "Administrative access required")
        return user
    except HTTPException: raise
    except Exception: raise HTTPException(401, "Authentication required")

class RecordPayload(BaseModel):
    values: dict = Field(default_factory=dict)

# Must precede the generic /api/{entity}/{item_id} route below. Otherwise
# FastAPI attempts to parse the literal word "pending" as an integer ID.
@app.get("/api/reviews/pending")
def pending_review_queue(request: Request):
    require_admin(request)
    return {"items": pending_records("dravya")}

@app.get("/api/{entity}")
def list_entity(entity: str, search: str = Query(""), limit: int = Query(50, ge=1, le=200)):
    table = {"dravya":"dravya","formulations":"formulations","anupana":"anupana_relationships","sources":"sources","passages":"source_passages"}.get(entity)
    if not table: return {"items": [], "error":"unsupported_entity"}
    return {"items": rows(table, search, limit), "development_only": True}

@app.get("/api/{entity}/{item_id}")
def get_entity(entity: str, item_id: int):
    table = {"dravya":"dravya","formulations":"formulations","anupana":"anupana_relationships","sources":"sources","passages":"source_passages"}.get(entity)
    if not table: return {"error":"unsupported_entity"}
    with connect() as db:
        row = db.execute(f"SELECT * FROM {table} WHERE id=?", (item_id,)).fetchone()
    return dict(row) if row else {"error":"not_found"}

@app.post("/api/{entity}", status_code=201)
def create_entity(entity: str, payload: RecordPayload, request: Request):
    require_admin(request)
    table = {"dravya":"dravya","synonyms":"dravya_synonyms","attributes":"dravya_attributes","formulations":"formulations","ingredients":"formulation_ingredients","anupana":"anupana_relationships","sources":"sources","passages":"source_passages","reviews":"expert_reviews"}.get(entity)
    if not table: raise HTTPException(404, "Unsupported entity")
    try: return write_record(table, payload.values)
    except (ValueError, LookupError) as exc: raise HTTPException(422, str(exc))
    except Exception: raise HTTPException(409, "Record could not be created")

@app.patch("/api/{entity}/{item_id}")
def update_entity(entity: str, item_id: int, payload: RecordPayload, request: Request):
    require_admin(request)
    table = {"dravya":"dravya","synonyms":"dravya_synonyms","attributes":"dravya_attributes","formulations":"formulations","ingredients":"formulation_ingredients","anupana":"anupana_relationships","sources":"sources","passages":"source_passages","reviews":"expert_reviews"}.get(entity)
    if not table: raise HTTPException(404, "Unsupported entity")
    try: return write_record(table, payload.values, item_id)
    except LookupError as exc: raise HTTPException(404, str(exc))
    except ValueError as exc: raise HTTPException(422, str(exc))
    except Exception: raise HTTPException(409, "Record could not be updated")

@app.delete("/api/{entity}/{item_id}", status_code=204)
def delete_entity(entity: str, item_id: int, request: Request):
    require_admin(request)
    table = {"dravya":"dravya","synonyms":"dravya_synonyms","attributes":"dravya_attributes","formulations":"formulations","ingredients":"formulation_ingredients","anupana":"anupana_relationships","sources":"sources","passages":"source_passages","reviews":"expert_reviews"}.get(entity)
    if not table: raise HTTPException(404, "Unsupported entity")
    try: delete_record(table, item_id)
    except LookupError as exc: raise HTTPException(404, str(exc))
    except Exception: raise HTTPException(409, "Record could not be deleted")

@app.post("/api/reviews/{entity}/{item_id}/approve")
def approve_entity(entity: str, item_id: int, payload: RecordPayload, request: Request):
    reviewer = require_admin(request)
    table = {"dravya":"dravya"}.get(entity)
    if not table: raise HTTPException(404, "Unsupported review entity")
    try: return approve_record(table, item_id, reviewer["email"], str(payload.values.get("review_notes", "")))
    except LookupError as exc: raise HTTPException(404, str(exc))
    except ValueError as exc: raise HTTPException(422, str(exc))

@app.get("/api/reviews/{entity}/{item_id}/history")
def review_history_route(entity: str, item_id: int, request: Request):
    require_admin(request)
    if entity != "dravya": raise HTTPException(404, "Unsupported review entity")
    return {"items": review_history(entity, item_id)}

@app.get("/api/reviews/{entity}/{item_id}")
def review_detail(entity: str, item_id: int, request: Request):
    require_admin(request)
    try:
        return review_detail_data(entity, item_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(404, str(exc))

@app.post("/api/reviews/{entity}/{item_id}/reject")
def reject_entity(entity: str, item_id: int, payload: RecordPayload, request: Request):
    reviewer = require_admin(request)
    table = {"dravya":"dravya"}.get(entity)
    if not table: raise HTTPException(404, "Unsupported review entity")
    try:
        if backend_name() != "postgresql":
            with connect() as db:
                if not db.execute(f"SELECT 1 FROM {table} WHERE id=?", (item_id,)).fetchone(): raise LookupError("Record not found")
                db.execute(f"UPDATE {table} SET review_status='rejected' WHERE id=?", (item_id,))
                db.execute("INSERT INTO expert_reviews(entity_type,entity_id,status,review_notes,reviewed_at) VALUES(?,?,?,?,datetime('now'))", (table,item_id,"rejected",str(payload.values.get("review_notes", ""))))
                return {"status":"rejected", "reviewer":reviewer["email"]}
        raise RuntimeError("PostgreSQL rejection requires repository implementation")
    except LookupError as exc: raise HTTPException(404, str(exc))
