"""Isolated retrieval over the development Charaka collection only."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from chromadb import PersistentClient

from config import EMBEDDING_MODEL_NAME
from models.embeddings import BGEEmbeddings

DEV_PERSIST_DIR = Path(__file__).resolve().parents[1] / "data" / "dev_chroma"
DEV_COLLECTION = "charaka_vanloon_dev"
PROVENANCE_TYPES = ("translated_source", "editor_note", "table", "unknown")


class DevelopmentRetriever:
    def __init__(self, *, persist_dir: Path = DEV_PERSIST_DIR, collection_name: str = DEV_COLLECTION,
                 model_name: str = EMBEDDING_MODEL_NAME, client: Any = None, embedder: Any = None) -> None:
        if Path(persist_dir).resolve() != DEV_PERSIST_DIR.resolve():
            raise ValueError("Development retriever may only use data/dev_chroma.")
        if collection_name != DEV_COLLECTION:
            raise ValueError("Development retriever may only use charaka_vanloon_dev.")
        self.client = client or PersistentClient(path=str(DEV_PERSIST_DIR))
        try:
            self.collection = self.client.get_collection(DEV_COLLECTION)
        except Exception as exc:
            raise RuntimeError("Development collection charaka_vanloon_dev is unavailable.") from exc
        recorded_model = (self.collection.metadata or {}).get("embedding_model")
        if recorded_model != model_name:
            raise ValueError(f"Development collection uses {recorded_model!r}, expected {model_name!r}.")
        self.model_name = model_name
        self.embedder = embedder or BGEEmbeddings(model_name=model_name, device="cpu")

    def search(self, query: str, *, top_k: int = 5, provenance: str | None = "translated_source") -> list[dict]:
        query = query.strip()
        if not query:
            raise ValueError("Query must not be empty.")
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")
        if provenance is not None and provenance not in PROVENANCE_TYPES:
            raise ValueError(f"Unsupported provenance filter: {provenance!r}.")
        where = {"provenance_role": provenance} if provenance else None
        result = self.collection.query(query_embeddings=[self.embedder.embed_query(query)], n_results=top_k,
                                       where=where, include=["documents", "metadatas", "distances"])
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        rows = []
        for rank, (chunk_id, text, metadata, distance) in enumerate(zip(ids, documents, metadatas, distances), 1):
            distance_value = float(distance)
            rows.append({"rank": rank, "id": chunk_id, "text": text, "metadata": metadata or {},
                         "distance": distance_value, "cosine_similarity": 1.0 - distance_value})
        return rows


def retrieve_dev(query: str, *, top_k: int = 5, provenance: str | None = "translated_source") -> list[dict]:
    return DevelopmentRetriever().search(query, top_k=top_k, provenance=provenance)
