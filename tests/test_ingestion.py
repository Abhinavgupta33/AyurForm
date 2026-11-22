"""Synthetic-only ingestion tests. No test fixture represents classical source material."""
import json
from pathlib import Path

import pytest
import pymupdf

from ingestion.chunk_text import build_chunks
from ingestion.create_embeddings import index_chunks, validate_chunks
from ingestion.extract_text import extract_pdf, save_extraction
from ingestion.review import file_sha256, make_review_manifest, validate_review
from ingestion.source_registry import validate_source_admission
import models.embeddings as embedding_module


def _synthetic_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "SYNTHETIC TEST FIXTURE. A neutral sample paragraph used to verify page extraction.")
    doc.new_page()  # blank page deliberately checks page preservation
    doc.save(path)
    doc.close()
    return path


def test_extraction_preserves_page_numbers_and_quality_report(tmp_path):
    pdf = _synthetic_pdf(tmp_path / "synthetic.pdf")
    output = extract_pdf(pdf, ocr="never")
    assert [page["page_number"] for page in output["pages"]] == [1, 2]
    assert output["pages"][0]["extraction_method"] == "digital"
    assert output["pages"][1]["extraction_method"] == "blank"
    assert output["quality"]["blank_pages"] == 1
    assert output["quality"]["pdf_page_count"] == 2


def test_extraction_does_not_invent_original_source_identifier(tmp_path):
    pdf = _synthetic_pdf(tmp_path / "synthetic.pdf")
    output = save_extraction(pdf, {"source_id": "synthetic", "source_title": "Synthetic fixture",
                                   "book_name": "Synthetic fixture", "license_note": "test only",
                                   "authorization": "synthetic fixture"}, tmp_path / "out", tmp_path / "meta", ocr="never")
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["source"]["source_id"] == "synthetic"
    assert "source_identifier" not in data["source"]
    assert len(data["source"]["source_sha256"]) == 64


def test_ocr_failure_reports_tesseract_requirement(monkeypatch, tmp_path):
    class FakePage:
        def get_text(self, *args, **kwargs):
            return ""

        def get_textpage_ocr(self, **kwargs):
            raise RuntimeError("Tesseract missing")

    class FakeDocument:
        def __len__(self):
            return 1

        def __iter__(self):
            return iter([FakePage()])

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("ingestion.extract_text.pymupdf.open", lambda _: FakeDocument())
    with pytest.raises(RuntimeError, match="Install Tesseract OCR"):
        extract_pdf(tmp_path / "synthetic-scan.pdf", ocr="auto")


def test_chunks_are_stable_and_preserve_only_known_provenance():
    doc = {"source": {"source_id": "synthetic", "source_title": "Synthetic test title",
                      "book_name": "Synthetic test book", "source_sha256": "abc"},
           "pages": [{"page_number": 4, "text": "Chapter 2: Sample heading.\n\nSYNTHETIC TEST FIXTURE. Neutral content."}]}
    first, second = build_chunks(doc), build_chunks(doc)
    assert first[0]["id"] == second[0]["id"]
    assert first[0]["metadata"]["page_number"] == 4
    assert first[0]["metadata"]["chapter_number"] == "2"
    assert first[0]["metadata"]["translator"] is None
    assert first[0]["metadata"]["verse_number"] is None


def test_review_manifest_binds_approval_to_exact_extraction(tmp_path):
    extraction = tmp_path / "pages.json"
    extraction.write_text(json.dumps({"source": {"source_id": "synthetic"}, "pages": [{"page_number": 1, "text": "synthetic"}]}), encoding="utf-8")
    phrase = f"APPROVE {file_sha256(extraction)[:12]}"
    manifest = make_review_manifest(extraction, "test reviewer", phrase)
    assert validate_review(extraction, manifest)["approved"] is True
    extraction.write_text(extraction.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        validate_review(extraction, manifest)


def test_review_rejects_incorrect_approval_phrase(tmp_path):
    extraction = tmp_path / "pages.json"
    extraction.write_text(json.dumps({"source": {"source_id": "synthetic"}, "pages": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="Approval must exactly match"):
        make_review_manifest(extraction, "reviewer", "APPROVE wrong")


def test_metadata_validation_rejects_missing_or_invalid_source_fields():
    with pytest.raises(ValueError, match="source_title"):
        validate_chunks([{"id": "x", "text": "synthetic", "metadata": {"source_id": "x", "book_name": "x", "page_number": 1}}])
    with pytest.raises(ValueError, match="page_number"):
        validate_chunks([{"id": "x", "text": "synthetic", "metadata": {"source_id": "x", "source_title": "x", "book_name": "x", "page_number": 0}}])


class FakeEmbedder:
    dimension = 3

    def embed_documents(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text):
        return [1.0, 0.0, 0.0]


def test_bge_wrapper_checks_dimension_and_uses_normalized_encode(monkeypatch):
    calls = []

    class FakeModel:
        def __init__(self, model_name, device):
            calls.append((model_name, device))

        def get_sentence_embedding_dimension(self):
            return 3

        def encode(self, texts, **kwargs):
            calls.append(kwargs)
            row = [1.0, 0.0, 0.0]
            return row if isinstance(texts, str) else [row for _ in texts]

    monkeypatch.setattr(embedding_module, "SentenceTransformer", FakeModel)
    embeddings = embedding_module.BGEEmbeddings(model_name="BAAI/bge-base-en-v1.5")
    assert len(embeddings.embed_query("synthetic query")) == 3
    assert len(embeddings.embed_documents(["synthetic document"])[0]) == 3
    assert calls[1]["normalize_embeddings"] is True
    assert calls[2]["normalize_embeddings"] is True
    assert embeddings.model_name == "BAAI/bge-base-en-v1.5"


def test_indexing_requires_review_and_verifies_retrieval_and_safe_reingest(tmp_path):
    extraction = tmp_path / "pages.json"
    extraction.write_text(json.dumps({"source": {"source_id": "synthetic", "source_sha256": "abc"},
                                      "pages": [{"page_number": 1, "text": "synthetic"}]}), encoding="utf-8")
    manifest = make_review_manifest(extraction, "synthetic reviewer", f"APPROVE {file_sha256(extraction)[:12]}")
    metadata = {"source_id": "synthetic", "source_sha256": "abc", "source_title": "Synthetic fixture",
                "book_name": "Synthetic fixture", "page_number": 1}
    chunks = [{"id": "synthetic-p1-c1", "text": "SYNTHETIC TEST FIXTURE; not classical text.", "metadata": metadata},
              {"id": "synthetic-p1-c2", "text": "Second synthetic fixture record.", "metadata": metadata}]
    result = index_chunks(chunks, extraction_path=extraction, review_manifest=manifest,
                          persist_dir=tmp_path / "db", collection_name="synthetic_test",
                          embedder=FakeEmbedder(), batch_size=1)
    assert result["source_records"] == 2
    assert result["retrieval_verified"] is True
    # Re-ingesting a reduced version updates existing IDs and removes stale records for this source only.
    reduced = index_chunks(chunks[:1], extraction_path=extraction, review_manifest=manifest,
                           persist_dir=tmp_path / "db", collection_name="synthetic_test",
                           embedder=FakeEmbedder())
    assert reduced["source_records"] == 1


def test_indexing_blocks_without_review_manifest(tmp_path):
    extraction = tmp_path / "pages.json"
    extraction.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="approval is missing"):
        index_chunks([], extraction_path=extraction, review_manifest=tmp_path / "missing.json")


def _admission_fixture(tmp_path, role="translated_source", usage_scope="production"):
    extraction = tmp_path / "approved-pages.json"
    extraction.write_text(json.dumps({"source": {"source_id": "approved", "source_sha256": "abc"},
                                      "pages": [{"page_number": 1, "text": "approved"}]}), encoding="utf-8")
    manifest = make_review_manifest(extraction, "approved reviewer", f"APPROVE {file_sha256(extraction)[:12]}")
    registry = {"source_id": "approved", "title": "Approved fixture", "translator": "Test translator",
                "editor": "Test editor", "publisher": "Test publisher", "edition": "Test edition",
                "publication_year": 2025, "rights_status": "verified", "permission_evidence_ref": "TEST-PERM-1",
                "review_status": "approved", "source_sha256": "abc", "usage_scope": usage_scope,
                "source_type": "synthetic_fixture", "provenance_classification": "translated_source"}
    metadata = {"source_id": "approved", "source_sha256": "abc", "source_title": "Approved fixture",
                "book_name": "Approved fixture", "page_number": 1, "provenance_role": role}
    chunks = [{"id": "approved-p1-c1", "text": "Approved synthetic passage.", "metadata": metadata}]
    return extraction, manifest, registry, chunks


def test_unapproved_source_is_rejected(tmp_path):
    extraction, manifest, registry, chunks = _admission_fixture(tmp_path)
    registry["review_status"] = "pending"
    with pytest.raises(ValueError, match="review_status"):
        index_chunks(chunks, extraction_path=extraction, review_manifest=manifest,
                     persist_dir=tmp_path / "db", collection_name="unapproved", embedder=FakeEmbedder(), source_registry=registry)


def test_unverified_rights_are_rejected(tmp_path):
    extraction, manifest, registry, chunks = _admission_fixture(tmp_path)
    registry["rights_status"] = "unverified"
    with pytest.raises(ValueError, match="rights"):
        index_chunks(chunks, extraction_path=extraction, review_manifest=manifest,
                     persist_dir=tmp_path / "db", collection_name="rights", embedder=FakeEmbedder(), source_registry=registry)


def test_unknown_provenance_is_rejected(tmp_path):
    extraction, manifest, registry, chunks = _admission_fixture(tmp_path, role="unknown")
    with pytest.raises(ValueError, match="provenance"):
        index_chunks(chunks, extraction_path=extraction, review_manifest=manifest,
                     persist_dir=tmp_path / "db", collection_name="provenance", embedder=FakeEmbedder(), source_registry=registry)


def test_approved_source_can_be_indexed_with_provenance(tmp_path):
    from chromadb import PersistentClient

    extraction, manifest, registry, chunks = _admission_fixture(tmp_path)
    client = PersistentClient(path=str(tmp_path / "approved-vectorstore"))
    result = index_chunks(chunks, extraction_path=extraction, review_manifest=manifest,
                          persist_dir=tmp_path / "db", collection_name="approved", embedder=FakeEmbedder(),
                          source_registry=registry, client=client)
    assert result["source_records"] == 1
    stored = client.get_collection("approved").get(ids=["approved-p1-c1"], include=["metadatas"])["metadatas"][0]
    assert stored["rights_status"] == "verified"
    assert stored["review_status"] == "approved"
    assert stored["usage_scope"] == "production"
    assert stored["permission_evidence_ref"] == "TEST-PERM-1"
    assert stored["translator"] == "Test translator"


def test_production_path_requires_registry_even_with_review(tmp_path, monkeypatch):
    extraction, manifest, registry, chunks = _admission_fixture(tmp_path)
    import ingestion.create_embeddings as embeddings
    monkeypatch.setattr(embeddings, "VECTORSTORE_DIR", tmp_path / "production")
    with pytest.raises(ValueError, match="Source registry approval"):
        index_chunks(chunks, extraction_path=extraction, review_manifest=manifest,
                     persist_dir=tmp_path / "production", collection_name="production", embedder=FakeEmbedder())


def test_registry_source_hash_change_invalidates_admission(tmp_path):
    extraction, manifest, registry, chunks = _admission_fixture(tmp_path)
    registry["source_sha256"] = "different-hash"
    with pytest.raises(ValueError, match="hash changed"):
        index_chunks(chunks, extraction_path=extraction, review_manifest=manifest,
                     persist_dir=tmp_path / "db", collection_name="hash", embedder=FakeEmbedder(), source_registry=registry)
