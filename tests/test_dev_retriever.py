from pathlib import Path

import pytest

from retrieval.dev_retriever import DEV_COLLECTION, DEV_PERSIST_DIR, DevelopmentRetriever
from retrieval import evaluate_dev_retrieval as evaluation


class FakeEmbedder:
    model_name = "BAAI/bge-base-en-v1.5"

    def embed_query(self, query):
        return [1.0, 0.0]


class FakeCollection:
    metadata = {"embedding_model": "BAAI/bge-base-en-v1.5"}

    def query(self, **kwargs):
        assert kwargs["n_results"] == 2
        assert kwargs["where"] == {"provenance_role": "translated_source"}
        return {"ids": [["id1", "id2"]], "documents": [["one", "two"]],
                "metadatas": [[{"pdf_page": 13, "provenance_role": "translated_source"}, {"pdf_page": 14, "provenance_role": "translated_source"}]],
                "distances": [[0.1, 0.3]]}


class FakeClient:
    def get_collection(self, name):
        assert name == DEV_COLLECTION
        return FakeCollection()


def test_dev_retriever_isolated_and_preserves_results():
    retriever = DevelopmentRetriever(persist_dir=DEV_PERSIST_DIR, client=FakeClient(), embedder=FakeEmbedder())
    rows = retriever.search("vata", top_k=2)
    assert rows[0]["metadata"]["pdf_page"] == 13
    assert rows[0]["cosine_similarity"] == pytest.approx(0.9)


def test_dev_retriever_rejects_production_paths():
    with pytest.raises(ValueError, match="only use data/dev_chroma"):
        DevelopmentRetriever(persist_dir=Path("vectorstore"), client=FakeClient(), embedder=FakeEmbedder())


def test_dev_retriever_validates_query_and_filter():
    retriever = DevelopmentRetriever(client=FakeClient(), embedder=FakeEmbedder())
    with pytest.raises(ValueError, match="must not be empty"):
        retriever.search("  ")
    with pytest.raises(ValueError, match="Unsupported provenance"):
        retriever.search("vata", provenance="translated_source_candidate")


def test_evaluation_dataset_has_per_query_filters():
    import json
    dataset = json.loads(evaluation.DATASET.read_text(encoding="utf-8"))
    filters = {row["id"]: row["provenance_filter"] for row in dataset}
    assert filters["q11"] == "editor_note"
    assert filters["q12"] == "table"
    assert filters["q15"] == "editor_note"
    assert filters["q14"] == "translated_source"


def test_evaluation_records_abstention_and_provenance(monkeypatch):
    class FakeRetriever:
        def search(self, query, *, top_k, provenance):
            return [{"rank": 1, "id": "chunk", "text": "excerpt", "metadata": {"provenance_role": "translated_source", "pdf_page": 2}, "distance": 0.9, "cosine_similarity": 0.1}]

    monkeypatch.setattr(evaluation, "DevelopmentRetriever", FakeRetriever)
    rows, metrics = evaluation.evaluate(top_k=5, abstention_distance=0.8)
    q14 = next(row for row in rows if row["id"] == "q14")
    assert q14["top_result"]["abstained"] is True
    assert q14["provenance_matches"] == [True]
    assert metrics["recall_at_5"] is None

