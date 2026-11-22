"""Run PDF extraction, a blocking human review checkpoint, chunking and Chroma indexing."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import EXTRACTED_DIR, METADATA_DIR, VECTORSTORE_DIR
from ingestion.chunk_text import build_chunks
from ingestion.create_embeddings import index_chunks
from ingestion.extract_text import save_extraction
from ingestion.review import make_review_manifest
from ingestion.source_registry import load_registry_entry


def run(args: argparse.Namespace, *, input_fn=input) -> dict:
    source = {"source_id": args.source_id or args.pdf.stem, "source_identifier": args.source_identifier,
              "book_name": args.book_name, "source_title": args.source_title, "sthana": args.sthana,
              "chapter": None, "edition": args.edition, "translator": args.translator,
              "license_note": args.license_note, "authorization": args.authorization}
    extraction_path = save_extraction(args.pdf, source, args.output_dir, args.metadata_dir,
                                      ocr=args.ocr, language=args.ocr_language, dpi=args.ocr_dpi)
    document = json.loads(extraction_path.read_text(encoding="utf-8"))
    print(f"Extraction ready: {extraction_path}\nQuality report: {json.dumps(document['quality'], ensure_ascii=False)}")
    print("Review the extracted pages and correct/verify metadata before continuing. Close this prompt only after review.")
    from ingestion.review import file_sha256
    expected = f"APPROVE {file_sha256(extraction_path)[:12]}"
    print(f"To continue, enter exactly: {expected}")
    entered = input_fn("Review approval: ").strip()
    if entered != expected:
        raise ValueError("Review not approved; stopped before chunking and indexing.")
    manifest = make_review_manifest(extraction_path, args.reviewer, entered)
    chunks = build_chunks(document, args.chunk_size, args.overlap)
    chunks_path = args.output_dir / f"{source['source_id']}_chunks.json"
    chunks_path.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    result = index_chunks(chunks, extraction_path=extraction_path, review_manifest=manifest,
                          persist_dir=args.persist_dir, collection_name=args.collection,
                          source_registry=args.source_registry)
    result.update({"extraction": str(extraction_path), "review_manifest": str(manifest), "chunks": str(chunks_path)})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--source-id")
    parser.add_argument("--source-identifier")
    parser.add_argument("--book-name", required=True)
    parser.add_argument("--source-title", required=True)
    parser.add_argument("--sthana")
    parser.add_argument("--edition")
    parser.add_argument("--translator")
    parser.add_argument("--license-note", required=True)
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--ocr", choices=("auto", "never", "always"), default="auto")
    parser.add_argument("--ocr-language", default="eng")
    parser.add_argument("--ocr-dpi", type=int, default=300)
    parser.add_argument("--chunk-size", type=int, default=1100)
    parser.add_argument("--overlap", type=int, default=140)
    parser.add_argument("--output-dir", type=Path, default=EXTRACTED_DIR)
    parser.add_argument("--metadata-dir", type=Path, default=METADATA_DIR)
    parser.add_argument("--persist-dir", type=Path, default=VECTORSTORE_DIR)
    parser.add_argument("--collection", default=None)
    parser.add_argument("--source-registry", type=Path, required=True)
    args = parser.parse_args()
    if args.collection is None:
        from config import CHROMA_COLLECTION
        args.collection = CHROMA_COLLECTION
    try:
        result = run(args)
    except (Exception, EOFError) as exc:
        parser.exit(2, f"Pipeline stopped: {exc}\n")
    print("Ingestion verified:\n" + json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
