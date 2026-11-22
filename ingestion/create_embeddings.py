"""Validate, embed, and safely upsert reviewed chunks into the configured ChromaDB."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chromadb import PersistentClient
from config import CHROMA_COLLECTION, EMBEDDING_MODEL_NAME, VECTORSTORE_DIR
from ingestion.review import validate_review
from ingestion.source_registry import (load_registry_entry, validate_development_admission,
                                       validate_provenance, validate_source_admission)
from models.embeddings import BGEEmbeddings

REQUIRED_META = ("source_id", "source_title", "book_name", "page_number")


def validate_chunks(chunks: list[dict], *, production: bool = False) -> None:
    if not chunks:
        raise ValueError("No chunks supplied.")
    ids: set[str] = set()
    source_hashes: set[tuple[str, str]] = set()
    for index, item in enumerate(chunks):
        if not isinstance(item.get("id"), str) or not item["id"].strip() or item["id"] in ids:
            raise ValueError(f"Chunk {index} has a missing or duplicate stable id.")
        ids.add(item["id"])
        if not isinstance(item.get("text"), str) or not item["text"].strip():
            raise ValueError(f"Chunk {item['id']} has empty text.")
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError(f"Chunk {item['id']} has no metadata object.")
        missing = [key for key in REQUIRED_META if metadata.get(key) in (None, "")]
        if missing:
            raise ValueError(f"Chunk {item['id']} is missing required source metadata: {', '.join(missing)}")
        try:
            page = int(metadata["page_number"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Chunk {item['id']} has invalid page_number.") from exc
        if page < 1:
            raise ValueError(f"Chunk {item['id']} has invalid page_number.")
        if not all(isinstance(v, (str, int, float, bool)) or v is None for v in metadata.values()):
            raise ValueError(f"Chunk {item['id']} has non-scalar Chroma metadata.")
        if metadata.get("source_sha256"):
            source_hashes.add((str(metadata["source_id"]), str(metadata["source_sha256"])))
        if production:
            validate_provenance(metadata.get("provenance_role"), production=True)
    if len(source_hashes) > 1:
        raise ValueError("A single ingestion batch cannot mix source ids or source file hashes.")


def chroma_metadata(values: dict) -> dict:
    metadata = {key: value for key, value in values.items() if value is not None and value != ""}
    metadata["page_number"] = int(metadata["page_number"])
    return metadata


def index_chunks(chunks: list[dict], *, review_manifest: Path, extraction_path: Path,
                 persist_dir: Path = VECTORSTORE_DIR, model_name: str = EMBEDDING_MODEL_NAME,
                 collection_name: str = CHROMA_COLLECTION, embedder: Any = None,
                 client: Any = None, batch_size: int = 64,
                 source_registry: dict | Path | None = None) -> dict:
    validate_review(extraction_path, review_manifest)
    extraction = json.loads(extraction_path.read_text(encoding="utf-8"))
    source_id = extraction["source"]["source_id"]
    expected_hash = extraction["source"].get("source_sha256")
    production = persist_dir.resolve() == VECTORSTORE_DIR.resolve()
    if production and source_registry is None:
        raise ValueError("Source registry approval is required for production indexing.")
    registry_entry = load_registry_entry(source_registry, source_id) if source_registry is not None else None
    if registry_entry is not None:
        if production or registry_entry.get("usage_scope") != "development_only":
            validate_source_admission(registry_entry, source_id=source_id, source_sha256=expected_hash)
        else:
            validate_development_admission(registry_entry, source_id=source_id, source_sha256=expected_hash)
    # Development-only registries may retain unknown provenance for later review;
    # only the configured production store applies the unknown-provenance block.
    enforce_provenance = production or bool(registry_entry and registry_entry.get("usage_scope") != "development_only")
    validate_chunks(chunks, production=enforce_provenance)
    if any(c["metadata"].get("source_id") != source_id for c in chunks):
        raise ValueError("Chunk source_id does not match the reviewed extraction.")
    if expected_hash and any(c["metadata"].get("source_sha256") != expected_hash for c in chunks):
        raise ValueError("Chunk source hash does not match the reviewed extraction.")
    if registry_entry is not None:
        # Carry the source-admission decision into Chroma so runtime retrieval
        # can enforce rights, scope and review status without inferring them.
        registry_fields = {
            "title": "source_title",
            "translator": "translator",
            "editor": "editor",
            "publisher": "publisher",
            "edition": "edition",
            "publication_year": "publication_year",
            "rights_status": "rights_status",
            "review_status": "review_status",
            "usage_scope": "usage_scope",
            "permission_evidence_ref": "permission_evidence_ref",
        }
        enriched_chunks = []
        for chunk in chunks:
            metadata = dict(chunk["metadata"])
            for registry_field, metadata_field in registry_fields.items():
                value = registry_entry.get(registry_field)
                if value not in (None, ""):
                    metadata[metadata_field] = value
            enriched_chunks.append({**chunk, "metadata": metadata})
        chunks = enriched_chunks
    embedder = embedder or BGEEmbeddings(model_name=model_name, device="cpu")
    texts = [chunk["text"] for chunk in chunks]
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        vectors.extend(embedder.embed_documents(texts[start:start + batch_size]))
    dimension = getattr(embedder, "dimension", None)
    if len(vectors) != len(texts) or any(not isinstance(v, list) or not v for v in vectors):
        raise ValueError("Embedding output count or shape does not match the input chunks.")
    if dimension is not None and any(len(v) != dimension for v in vectors):
        raise ValueError(f"Embedding dimensions do not match model dimension {dimension}.")
    if client is None:
        persist_dir.mkdir(parents=True, exist_ok=True)
        client = PersistentClient(path=str(persist_dir))
    collection = client.get_or_create_collection(collection_name, metadata={"hnsw:space": "cosine", "embedding_model": model_name})
    recorded_model = (collection.metadata or {}).get("embedding_model")
    if collection.count() and recorded_model != model_name:
        raise ValueError(
            f"Collection '{collection_name}' contains {collection.count()} records but does not confirm "
            f"embedding model {model_name!r} (recorded: {recorded_model!r}). Use the matching model or a new collection."
        )
    if not collection.count() and recorded_model != model_name:
        metadata = dict(collection.metadata or {})
        metadata.update({"hnsw:space": "cosine", "embedding_model": model_name})
        collection.modify(metadata=metadata)
    old_ids = collection.get(where={"source_id": source_id}, include=["metadatas"]).get("ids", [])
    ids = [c["id"] for c in chunks]
    # Upsert in bounded requests. Remove stale ids for this source only after all new batches succeed.
    for start in range(0, len(chunks), batch_size):
        stop = start + batch_size
        collection.upsert(ids=ids[start:stop], documents=texts[start:stop],
                          metadatas=[chroma_metadata(c["metadata"]) for c in chunks[start:stop]],
                          embeddings=vectors[start:stop])
    stale = sorted(set(old_ids) - set(ids))
    if stale:
        for start in range(0, len(stale), batch_size):
            collection.delete(ids=stale[start:start + batch_size])
    count = collection.count()
    source_records = collection.get(where={"source_id": source_id}, include=["metadatas"])
    source_count = len(source_records.get("ids", []))
    if source_count != len(chunks):
        raise RuntimeError(f"Index verification failed: expected {len(chunks)} source records, found {source_count}.")
    # Retrieval smoke check uses the same BGE document/query wrapper and collection actually written.
    query_vector = embedder.embed_query(texts[0])
    result = collection.query(query_embeddings=[query_vector], n_results=1, where={"source_id": source_id}, include=["documents", "metadatas", "distances"])
    retrieved_ids = (result.get("ids") or [[]])[0]
    if not retrieved_ids:
        raise RuntimeError("Index verification failed: no passage was retrieved from the written source.")
    return {"source_id": source_id, "source_records": source_count, "collection_count": count,
            "model_name": model_name, "embedding_dimension": len(vectors[0]),
            "retrieval_verified": True, "retrieved_id": retrieved_ids[0],
            "retrieved_metadata": (result.get("metadatas") or [[]])[0][0]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--review-manifest", type=Path, required=True)
    parser.add_argument("--persist-dir", type=Path, default=VECTORSTORE_DIR)
    parser.add_argument("--collection", default=CHROMA_COLLECTION)
    parser.add_argument("--source-registry", type=Path, required=True)
    args = parser.parse_args()
    try:
        chunks = json.loads(args.chunks.read_text(encoding="utf-8"))
        result = index_chunks(chunks, extraction_path=args.extraction, review_manifest=args.review_manifest,
                              persist_dir=args.persist_dir, collection_name=args.collection,
                              source_registry=args.source_registry)
    except Exception as exc:
        parser.exit(2, f"Indexing failed: {exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
