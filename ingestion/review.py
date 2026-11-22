"""Human review checkpoint utilities for source extraction artifacts."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def make_review_manifest(extraction_path: Path, reviewer: str, approval_phrase: str, output: Path | None = None) -> Path:
    if not reviewer.strip():
        raise ValueError("Reviewer name/identifier is required.")
    payload = json.loads(extraction_path.read_text(encoding="utf-8"))
    digest = file_sha256(extraction_path)
    expected = f"APPROVE {digest[:12]}"
    if approval_phrase.strip() != expected:
        raise ValueError(f"Approval must exactly match: {expected}")
    manifest = {"schema_version": 1, "approved": True, "reviewer": reviewer.strip(),
                "approved_at_utc": datetime.now(timezone.utc).isoformat(),
                "extraction_file": extraction_path.name, "extraction_sha256": digest,
                "source_id": payload["source"]["source_id"], "page_count": len(payload["pages"])}
    target = output or extraction_path.with_name("review_approval.json")
    target.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return target


def validate_review(extraction_path: Path, manifest_path: Path) -> dict:
    if not manifest_path.is_file():
        raise ValueError("Human review approval is missing; indexing is blocked.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = json.loads(extraction_path.read_text(encoding="utf-8"))
    if manifest.get("approved") is not True or not manifest.get("reviewer"):
        raise ValueError("Review manifest is not explicitly approved by a reviewer.")
    if manifest.get("extraction_sha256") != file_sha256(extraction_path):
        raise ValueError("Reviewed extraction has changed; review it again before proceeding.")
    if manifest.get("source_id") != payload.get("source", {}).get("source_id") or manifest.get("page_count") != len(payload.get("pages", [])):
        raise ValueError("Review manifest does not match this extraction/source.")
    return manifest
