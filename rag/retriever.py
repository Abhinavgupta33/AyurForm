"""ChromaDB retrieval over the local Charaka passage collection."""

from __future__ import annotations

import time
from pathlib import Path

from chromadb import PersistentClient

from config import ACTIVE_CHROMA_COLLECTION, ACTIVE_VECTORSTORE_DIR, TOP_K
from models.embeddings import BGEEmbeddings
from utils.diagnostics import LOGGER


class EmbeddingError(RuntimeError):
    """The configured BGE model could not be loaded or embed the query."""


class ChromaRetrievalError(RuntimeError):
    """The configured Chroma collection could not be queried."""


class PassageRetriever:
    def __init__(self, persist_dir: Path = ACTIVE_VECTORSTORE_DIR, collection_name: str = ACTIVE_CHROMA_COLLECTION, embedder=None):
        try:
            self.client = PersistentClient(path=str(persist_dir))
            self.collection = self.client.get_or_create_collection(collection_name, metadata={"hnsw:space": "cosine"})
        except Exception as exc:
            LOGGER.error("retrieval stage=chroma_initialize outcome=failed exception=%s", type(exc).__name__)
            raise ChromaRetrievalError("The configured Chroma collection could not be initialized.") from exc
        self.embedder = embedder

    def retrieve(self, query: str, top_k: int = TOP_K, *, request_id: str | None = None) -> list[dict]:
        request = f" correlation={request_id}" if request_id else ""
        started = time.monotonic()
        try:
            collection_count = self.collection.count()
        except Exception as exc:
            LOGGER.error("retrieval stage=chroma_count%s outcome=failed exception=%s", request, type(exc).__name__)
            raise ChromaRetrievalError("The Chroma collection could not be read.") from exc
        if collection_count == 0:
            LOGGER.info("retrieval stage=complete%s outcome=empty collection_count=0 query_embedding_skipped=true duration_ms=%d", request, int((time.monotonic() - started) * 1000))
            return []
        if self.embedder is None:
            load_started = time.monotonic()
            try:
                self.embedder = BGEEmbeddings(device="cpu")
            except Exception as exc:
                LOGGER.error("retrieval stage=embedding_model_load%s outcome=failed exception=%s duration_ms=%d", request, type(exc).__name__, int((time.monotonic() - load_started) * 1000))
                raise EmbeddingError("The configured BGE embedding model could not be loaded.") from exc
            LOGGER.info("retrieval stage=embedding_model_load%s outcome=success duration_ms=%d model=%s", request, int((time.monotonic() - load_started) * 1000), getattr(self.embedder, "model_name", "configured BGE"))
        embedding_started = time.monotonic()
        try:
            vector = self.embedder.embed_query(query)
            dimension = len(vector)
        except Exception as exc:
            LOGGER.error("retrieval stage=query_embedding%s outcome=failed exception=%s duration_ms=%d", request, type(exc).__name__, int((time.monotonic() - embedding_started) * 1000))
            raise EmbeddingError("The BGE query embedding could not be generated.") from exc
        LOGGER.info("retrieval stage=query_embedding%s outcome=success duration_ms=%d dimension=%d", request, int((time.monotonic() - embedding_started) * 1000), dimension)
        chroma_started = time.monotonic()
        try:
            result = self.collection.query(query_embeddings=[vector], n_results=min(top_k, collection_count))
        except Exception as exc:
            LOGGER.error("retrieval stage=chroma_query%s outcome=failed exception=%s duration_ms=%d", request, type(exc).__name__, int((time.monotonic() - chroma_started) * 1000))
            raise ChromaRetrievalError("ChromaDB could not retrieve passages from the selected collection.") from exc
        try:
            documents = result.get("documents", [[]])[0]
            ids = result.get("ids", [[]])[0]
            metadatas = result.get("metadatas", [[]])[0]
            distances = result.get("distances", [[]])[0]
            hits = [
                {"id": pid, "text": text, "metadata": {**(metadata or {}), **({"usage_scope": "development_only"} if getattr(self.collection, "name", "") == "charaka_vanloon_dev" else {})}, "distance": distance}
                for pid, text, metadata, distance in zip(ids, documents, metadatas, distances)
            ]
        except Exception as exc:
            LOGGER.error("retrieval stage=chroma_result_parse%s outcome=failed exception=%s", request, type(exc).__name__)
            raise ChromaRetrievalError("ChromaDB returned an invalid retrieval result.") from exc
        LOGGER.info("retrieval stage=chroma_query%s outcome=success duration_ms=%d passage_count=%d", request, int((time.monotonic() - chroma_started) * 1000), len(hits))
        LOGGER.info("retrieval stage=complete%s outcome=success collection_count=%d passage_count=%d duration_ms=%d", request, collection_count, len(hits), int((time.monotonic() - started) * 1000))
        return hits


def get_retriever() -> PassageRetriever:
    return PassageRetriever()
