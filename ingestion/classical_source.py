"""Rights-pending, development-only PDF intake. Never writes to ChromaDB."""
from __future__ import annotations
import hashlib, json, re, tempfile
from pathlib import Path
from ingestion.extract_text import extract_pdf
from ingestion.chunk_text import split_text, detect_chapter, classify_provenance

DEV_SOURCE_DIR = Path(__file__).resolve().parents[1] / "data" / "development_sources"

def eligible_for_public_retrieval(source: dict) -> bool:
    return source.get("rights_status") in {"verified", "licensed", "public_domain"} and source.get("review_status") == "approved" and source.get("usage_scope") == "production"

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def ingest_pdf_bytes(data: bytes, metadata: dict, *, output_dir: Path = DEV_SOURCE_DIR) -> dict:
    if not data:
        raise ValueError("The uploaded PDF is empty.")
    if not metadata.get("title"):
        raise ValueError("Source title is required.")
    digest = sha256_bytes(data); output_dir.mkdir(parents=True, exist_ok=True)
    registry = output_dir / "registry.json"
    entries = json.loads(registry.read_text(encoding="utf-8")) if registry.exists() else {"sources": []}
    if any(x.get("source_sha256") == digest for x in entries["sources"]):
        raise ValueError("This exact PDF has already been ingested (checksum duplicate).")
    with tempfile.TemporaryDirectory() as temp_dir:
        pdf_path=Path(temp_dir)/"source.pdf"
        pdf_path.write_bytes(data)
        extracted = extract_pdf(pdf_path, ocr="never")
    source_id = "dev-" + digest[:16]
    source = {"source_id":source_id, "title":metadata["title"], "author_editor":metadata.get("author_editor"),
              "translator":metadata.get("translator"), "language":metadata.get("language"), "edition":metadata.get("edition"),
              "publisher":metadata.get("publisher"), "publication_year":metadata.get("publication_year"),
              "source_sha256":digest, "copyright_status":"rights_pending", "rights_status":"pending",
              "usage_scope":"development_only", "review_status":"pending"}
    passages=[]; chapter=None; section=None
    for page in extracted["pages"]:
        lines=page["text"].splitlines()
        detected, title=detect_chapter(page["text"])
        if detected: chapter, section=detected,title
        for index, text in enumerate(split_text(page["text"], chunk_size=1100, overlap=100),1):
            provenance=classify_provenance(text,page_number=page["page_number"])
            pid=f"{source_id}-pg{page['page_number']}-part{index}-{hashlib.sha256(text.encode()).hexdigest()[:10]}"
            passages.append({"source_id":source_id,"passage_id":pid,"page_number":page["page_number"],"chapter":chapter,"section":section,
                             "original_text":text,"translation_status":"unverified","evidence_classification":provenance,
                             "provenance_role":provenance,"usage_scope":"development_only","review_status":"pending"})
    result={"source":source,"quality":extracted["quality"],"passages":passages,
            "statistics":{"page_count":extracted["quality"]["pdf_page_count"],"empty_pages":extracted["quality"]["blank_pages"],
                           "extracted_characters":extracted["quality"]["total_characters"],"passage_count":len(passages),
                           "page_coverage":sorted({p["page_number"] for p in passages})}}
    (output_dir/f"{source_id}.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    entries["sources"].append(source); registry.write_text(json.dumps(entries,ensure_ascii=False,indent=2),encoding="utf-8")
    return result
