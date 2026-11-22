from pathlib import Path

import rag.retriever as retriever_module


class Embedder:
    model_name = "BAAI/bge-base-en-v1.5"
    def embed_query(self, query): return [1.0, 0.0]


class Collection:
    name = "charaka_vanloon_dev"
    metadata = {"embedding_model": "BAAI/bge-base-en-v1.5"}
    def count(self): return 1
    def query(self, **kwargs):
        return {"ids": [["x"]], "documents": [["text"]], "metadatas": [[{"provenance_role": "translated_source"}]], "distances": [[.1]]}


class Client:
    def __init__(self, path): self.path = path
    def get_collection(self, name):
        self.name = name
        return Collection()
    def get_or_create_collection(self, name, metadata=None):
        return Collection()


def test_development_retriever_marks_scope_and_uses_dev_collection(monkeypatch, tmp_path):
    client = Client(tmp_path)
    monkeypatch.setattr(retriever_module, "PersistentClient", lambda path: client)
    obj = retriever_module.PassageRetriever(persist_dir=tmp_path, collection_name="charaka_vanloon_dev", embedder=Embedder())
    rows = obj.retrieve("vata", 1)
    assert rows[0]["metadata"]["usage_scope"] == "development_only"


def test_production_defaults_remain_separate():
    assert retriever_module.ACTIVE_VECTORSTORE_DIR.name in {"vectorstore", "dev_chroma"}
    assert retriever_module.ACTIVE_CHROMA_COLLECTION in {"charaka_samhita", "charaka_vanloon_dev"}
