import fitz
import pytest
from ingestion.classical_source import ingest_pdf_bytes, eligible_for_public_retrieval

def pdf_bytes(text):
    doc=fitz.open(); page=doc.new_page(); page.insert_text((72,72),text); data=doc.tobytes(); doc.close(); return data

def test_ingestion_preserves_page_and_source_provenance_pending(tmp_path):
    data=pdf_bytes("Chapter 2: Example\n\nSu1#41 A source paragraph with sufficient words to extract.")
    result=ingest_pdf_bytes(data,{"title":"Synthetic test fixture"},output_dir=tmp_path)
    assert result["statistics"]["page_count"] == 1
    passage=result["passages"][0]
    assert passage["page_number"] == 1
    assert passage["passage_id"].startswith(result["source"]["source_id"])
    assert passage["original_text"]
    assert passage["usage_scope"] == "development_only"
    assert result["source"]["rights_status"] == "pending"
    assert not eligible_for_public_retrieval(result["source"])

def test_empty_pdf_page_is_counted_and_not_passaged(tmp_path):
    doc=fitz.open(); doc.new_page(); page=doc.new_page(); page.insert_text((72,72),"A page with enough words to ensure extraction succeeds for the fixture."); data=doc.tobytes(); doc.close()
    result=ingest_pdf_bytes(data,{"title":"Two page fixture"},output_dir=tmp_path)
    assert result["statistics"]["page_count"] == 2
    assert result["statistics"]["empty_pages"] == 1
    assert all(p["page_number"] == 2 for p in result["passages"])

def test_duplicate_checksum_and_empty_pdf_are_rejected(tmp_path):
    data=pdf_bytes("A test paragraph with enough words for extraction and page coverage.")
    ingest_pdf_bytes(data,{"title":"Fixture"},output_dir=tmp_path)
    with pytest.raises(ValueError,match="checksum duplicate"):
        ingest_pdf_bytes(data,{"title":"Fixture"},output_dir=tmp_path)
    with pytest.raises(ValueError,match="empty"):
        ingest_pdf_bytes(b"",{"title":"Fixture"},output_dir=tmp_path)
