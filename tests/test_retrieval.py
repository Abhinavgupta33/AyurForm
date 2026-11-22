from pathlib import Path

from ingestion.chunk_text import build_chunks, split_text
from utils.citations import format_reference, validate_passage_ids


def test_split_text_respects_chunk_limit_and_keeps_content():
    text = " ".join(["classical passage"] * 300)
    chunks = split_text(text, chunk_size=400, overlap=50)
    assert len(chunks) > 1
    assert all(len(chunk) <= 400 for chunk in chunks)
    assert all("classical" in chunk for chunk in chunks)


def test_chunk_metadata_uses_only_explicit_source_fields():
    document = {
        "source": {"source_id": "charaka", "source_title": "Edition A", "book_name": "Charaka Samhita", "translator": "A Translator"},
        "pages": [{"page_number": 17, "text": "Chapter 2: Nidana.\n\nA sample verse 4 appears here."}],
    }
    chunks = build_chunks(document)
    assert chunks[0]["metadata"]["page_number"] == 17
    assert chunks[0]["metadata"]["chapter_number"] == "2"
    assert chunks[0]["metadata"]["verse_number"] == "4"
    assert chunks[0]["metadata"]["sthana"] is None


def test_reference_omits_missing_verse_and_chapter_details():
    reference = format_reference({"book_name": "Charaka Samhita", "page_number": 9})
    assert reference == "Charaka Samhita · PDF page 9"
    assert "Verse" not in reference
    assert "Chapter" not in reference


def test_passage_id_validation_rejects_model_invented_ids():
    passages = [{"id": "x"}, {"id": "y"}]
    assert validate_passage_ids(["P1", "P99", "P2"], passages) == ["P1", "P2"]
