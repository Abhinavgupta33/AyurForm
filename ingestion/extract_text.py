"""Extract page-preserving text from an authorized PDF; OCR is optional via Tesseract."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pymupdf
from config import EXTRACTED_DIR, METADATA_DIR


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_page_text(text: str) -> str:
    text = text.replace("\u00ad", "").replace("\x00", "")
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_pdf(pdf_path: Path, ocr: str = "auto", language: str = "eng", dpi: int = 300) -> dict:
    """Return all source pages and quality diagnostics. `auto` OCRs pages with little digital text."""
    if ocr not in {"auto", "never", "always"}:
        raise ValueError("ocr must be auto, never, or always")
    pages, counts, warnings = [], {"digital": 0, "ocr": 0, "blank": 0}, []
    try:
        document = pymupdf.open(pdf_path)
    except Exception as exc:
        raise ValueError(f"Could not open PDF {pdf_path}: {exc}") from exc
    with document:
        page_count = len(document)
        if not page_count:
            raise ValueError("The PDF contains no pages.")
        for number, page in enumerate(document, 1):
            digital = clean_page_text(page.get_text("text", sort=True))
            text, method = digital, "digital"
            # OCR likely scan pages only where little machine-readable text exists.
            needs_ocr = ocr == "always" or (ocr == "auto" and len(digital) < 40)
            if needs_ocr:
                try:
                    textpage = page.get_textpage_ocr(language=language, dpi=dpi, full=True)
                    scanned = clean_page_text(page.get_text("text", textpage=textpage, sort=True))
                    if len(scanned) > len(digital):
                        text, method = scanned, "ocr"
                except Exception as exc:
                    if ocr == "always" or not digital:
                        raise RuntimeError(
                            f"OCR failed on PDF page {number}. Install Tesseract OCR and its '{language}' data, "
                            f"or use --ocr never for a digital PDF. Details: {exc}"
                        ) from exc
                    warnings.append(f"Page {number}: OCR attempt failed; retained digital text ({exc}).")
            if text:
                counts[method] += 1
            else:
                method = "blank"
                counts["blank"] += 1
                warnings.append(f"Page {number}: no text extracted; inspect this page manually.")
            if len(text) < 40 and text:
                warnings.append(f"Page {number}: unusually little text ({len(text)} characters); inspect extraction.")
            pages.append({"page_number": number, "text": text, "extraction_method": method})
    total_chars = sum(len(p["text"]) for p in pages)
    if total_chars == 0:
        raise ValueError("No text extracted. The PDF may be image-only; configure Tesseract OCR and retry.")
    return {
        "pages": pages,
        "quality": {
            "pdf_page_count": page_count, "page_records": len(pages), "digital_pages": counts["digital"],
            "ocr_pages": counts["ocr"], "blank_pages": counts["blank"], "total_characters": total_chars,
            "warnings": warnings,
        },
    }


def save_extraction(pdf_path: Path, source: dict, output_dir: Path, metadata_dir: Path, *, ocr: str = "auto", language: str = "eng", dpi: int = 300) -> Path:
    if not source.get("authorization") or not source.get("license_note"):
        raise ValueError("Record both the authorization basis and license/permission note.")
    if not source.get("source_title") or not source.get("book_name"):
        raise ValueError("Provide the source title and book name as printed/identified.")
    source_id = re.sub(r"[^A-Za-z0-9_-]+", "_", source.get("source_id", pdf_path.stem)).strip("_")
    if not source_id:
        raise ValueError("Provide a valid source_id.")
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)
    result = extract_pdf(pdf_path, ocr=ocr, language=language, dpi=dpi)
    source = {key: value for key, value in source.items() if value not in ("", None)}
    source.update({"source_id": source_id, "source_file": pdf_path.name,
                   "source_sha256": sha256_file(pdf_path),
                   "extracted_at_utc": datetime.now(timezone.utc).isoformat()})
    document = {"schema_version": 1, "source": source, "quality": result["quality"], "pages": result["pages"]}
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / f"{source_id}_pages.json"
    out.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    (metadata_dir / f"{source_id}.json").write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--source-id", help="Stable identifier from your source registry; defaults to filename stem")
    parser.add_argument("--source-identifier", help="Original source identifier, if present")
    parser.add_argument("--source-title", required=True)
    parser.add_argument("--book-name", required=True)
    parser.add_argument("--sthana", help="Only provide when confirmed from the source")
    parser.add_argument("--edition", help="Edition details, if printed")
    parser.add_argument("--translator", help="Translator/editor, if printed")
    parser.add_argument("--license-note", required=True)
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--ocr", choices=("auto", "never", "always"), default="auto")
    parser.add_argument("--ocr-language", default="eng")
    parser.add_argument("--ocr-dpi", type=int, default=300)
    parser.add_argument("--output-dir", type=Path, default=EXTRACTED_DIR)
    parser.add_argument("--metadata-dir", type=Path, default=METADATA_DIR)
    a = parser.parse_args()
    source = {"source_id": a.source_id or a.pdf.stem, "source_identifier": a.source_identifier,
              "book_name": a.book_name, "source_title": a.source_title, "sthana": a.sthana,
              "edition": a.edition, "translator": a.translator, "license_note": a.license_note,
              "authorization": a.authorization}
    try:
        output = save_extraction(a.pdf, source, a.output_dir, a.metadata_dir, ocr=a.ocr, language=a.ocr_language, dpi=a.ocr_dpi)
    except Exception as exc:
        parser.exit(2, f"Extraction failed: {exc}\n")
    payload = json.loads(output.read_text(encoding="utf-8"))
    print(f"Extracted {payload['quality']['page_records']} pages ({payload['quality']['total_characters']} characters) to {output}")
    print(json.dumps(payload["quality"], ensure_ascii=False, indent=2))
    print("STOP: inspect every page and its chapter/verse markers before creating a review approval.")


if __name__ == "__main__":
    main()
