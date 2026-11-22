import pytest

import rag.retriever as module
from rag.retriever import ChromaRetrievalError, EmbeddingError, PassageRetriever


class StubCollection:
    def __init__(self, *, count=1, error=None, name="charaka_vanloon_dev"):
        self.count_value = count
        self.error = error
        self.name = name
        self.query_calls = []

    def count(self):
        return self.count_value

    def query(self, **kwargs):
        self.query_calls.append(kwargs)
        if self.error:
            raise self.error
        return {
            "ids": [["stable-1"]],
            "documents": [["A complete source passage."]],
            "metadatas": [[{"provenance_role": "translated_source", "page_number": 7}]],
            "distances": [[0.2]],
        }


class StubClient:
    def __init__(self, collection):
        self.collection = collection

    def get_or_create_collection(self, *args, **kwargs):
        return self.collection


class StubEmbedder:
    model_name = "BAAI/bge-base-en-v1.5"

    def __init__(self, error=None):
        self.error = error
        self.queries = []

    def embed_query(self, query):
        self.queries.append(query)
        if self.error:
            raise self.error
        return [0.1] * 768


def make_retriever(monkeypatch, collection, embedder=None):
    monkeypatch.setattr(module, "PersistentClient", lambda **kwargs: StubClient(collection))
    return PassageRetriever(embedder=embedder)


def test_query_embedding_and_chroma_stages_keep_correlation_and_rights_scope(monkeypatch, caplog):
    collection = StubCollection()
    embedder = StubEmbedder()
    retriever = make_retriever(monkeypatch, collection, embedder)

    hits = retriever.retrieve("private question text", top_k=5, request_id="retrieval-corr-1")

    assert hits[0]["id"] == "stable-1"
    assert hits[0]["metadata"]["usage_scope"] == "development_only"
    assert collection.query_calls[0]["query_embeddings"] == [[0.1] * 768]
    assert "stage=query_embedding correlation=retrieval-corr-1 outcome=success duration_ms=" in caplog.text
    assert "stage=chroma_query correlation=retrieval-corr-1 outcome=success duration_ms=" in caplog.text
    assert "private question text" not in caplog.text


def test_empty_collection_skips_bge_loading_and_chroma_query(monkeypatch):
    collection = StubCollection(count=0)
    retriever = make_retriever(monkeypatch, collection)
    monkeypatch.setattr(module, "BGEEmbeddings", lambda **kwargs: pytest.fail("Empty collection must not load BGE"))
    assert retriever.retrieve("question", request_id="empty-corr") == []
    assert collection.query_calls == []


def test_embedding_failure_is_distinguished_from_chroma_failure(monkeypatch):
    collection = StubCollection()
    retriever = make_retriever(monkeypatch, collection, StubEmbedder(RuntimeError("encoder failed")))
    with pytest.raises(EmbeddingError):
        retriever.retrieve("question", request_id="embedding-corr")
    assert collection.query_calls == []


def test_bge_model_loading_failure_is_distinguished(monkeypatch):
    collection = StubCollection()
    retriever = make_retriever(monkeypatch, collection)
    monkeypatch.setattr(module, "BGEEmbeddings", lambda **kwargs: (_ for _ in ()).throw(OSError("download unavailable")))
    with pytest.raises(EmbeddingError, match="could not be loaded"):
        retriever.retrieve("question", request_id="load-bge-corr")


def test_chroma_query_failure_is_distinguished(monkeypatch):
    collection = StubCollection(error=RuntimeError("query failed"))
    retriever = make_retriever(monkeypatch, collection, StubEmbedder())
    with pytest.raises(ChromaRetrievalError, match="could not retrieve"):
        retriever.retrieve("question", request_id="chroma-corr")
