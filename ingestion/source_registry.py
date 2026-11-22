"""Source admission and provenance controls for production ingestion."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROVENANCE_ROLES = {
    "translated_source", "editorial_commentary", "translator_note",
    "editor_note", "table", "unknown",
}
APPROVED_RIGHTS = {"verified", "licensed", "public_domain"}
REQUIRED_FIELDS = (
    "source_id", "title", "translator", "editor", "publisher", "edition",
    "publication_year", "rights_status", "permission_evidence_ref", "review_status",
)


def load_registry_entry(registry: dict[str, Any] | Path, source_id: str | None = None) -> dict[str, Any]:
    if isinstance(registry, Path):
        if not registry.is_file():
            raise ValueError("Source registry is missing; production indexing is blocked.")
        payload = json.loads(registry.read_text(encoding="utf-8"))
    else:
        payload = registry
    entries = payload.get("sources", []) if isinstance(payload, dict) else []
    if isinstance(payload, dict) and payload.get("source_id"):
        entries = [payload]
    if not isinstance(entries, list):
        raise ValueError("Source registry must contain a sources list.")
    matches = [entry for entry in entries if isinstance(entry, dict) and (source_id is None or entry.get("source_id") == source_id)]
    if len(matches) != 1:
        raise ValueError("Source registry must contain exactly one matching source entry.")
    return matches[0]


def validate_source_admission(entry: dict[str, Any], *, source_id: str, source_sha256: str | None = None) -> None:
    missing = [key for key in REQUIRED_FIELDS if entry.get(key) in (None, "")]
    if missing:
        raise ValueError(f"Source registry entry is missing required fields: {', '.join(missing)}")
    if entry.get("source_id") != source_id:
        raise ValueError("Source registry source_id does not match the extraction.")
    if str(entry.get("rights_status")).casefold() not in APPROVED_RIGHTS:
        raise ValueError("Source rights are not verified/licensed/public-domain; production indexing is blocked.")
    if str(entry.get("review_status")).casefold() != "approved":
        raise ValueError("Source review_status is not approved; production indexing is blocked.")
    if source_sha256 and entry.get("source_sha256") and entry["source_sha256"] != source_sha256:
        raise ValueError("Source hash changed since registry approval; re-review is required.")


def validate_development_admission(entry: dict[str, Any], *, source_id: str, source_sha256: str | None = None) -> None:
    """Allow explicitly scoped local development material without granting production approval."""
    missing = [key for key in ("source_id", "title", "usage_scope", "source_type", "provenance_classification") if entry.get(key) in (None, "")]
    if missing:
        raise ValueError(f"Development registry entry is missing required fields: {', '.join(missing)}")
    if entry.get("source_id") != source_id:
        raise ValueError("Development registry source_id does not match the extraction.")
    if entry.get("usage_scope") != "development_only":
        raise ValueError("Development ingestion requires usage_scope=development_only.")
    if source_sha256 and entry.get("source_sha256") and entry["source_sha256"] != source_sha256:
        raise ValueError("Development source hash does not match the extracted PDF.")


def validate_provenance(role: Any, *, production: bool) -> None:
    if role not in PROVENANCE_ROLES:
        raise ValueError(f"Unsupported content provenance role: {role!r}")
    if production and role == "unknown":
        raise ValueError("Unknown content provenance is not allowed in production indexing.")
