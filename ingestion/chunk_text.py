"""Create deterministic, page-traceable chunks after human review."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingestion.review import validate_review

CHAPTER_PATTERN = re.compile(r"^\s*(?:chapter|adhyaya|adhyāya)\s+(?:no\.\s*)?([\w.-]+)(?:\s*[:.\-–]\s*(.{2,120}))?\s*$", re.I)
VERSE_PATTERN = re.compile(r"\b(?:verse|śloka|shloka|sūtra|sutra)\s+([\d.]+[a-z]?)", re.I)
REFERENCE_PATTERN = re.compile(r"\b(?:Su|Vi|Ni|Sa|In|Ci|Ka|Si)\s*\d+\s*#\s*\d+(?:\s*[-–]\s*\d+)?\b", re.I)
EDITOR_PATTERN = re.compile(r"(?:\[|\{|\]|\}|\b(?:editor|consider moving|to be inserted|look up|chapter\?)\b|\*{1,2})", re.I)


def classify_provenance(text: str, *, page_number: int) -> str:
    """Conservative classification: only explicit editorial/table signals are labeled."""
    if re.search(r"(?im)\b(?:table of contents|section name|abbreviation|number of chapters)\b", text):
        return "table"
    if EDITOR_PATTERN.search(text):
        return "editor_note"
    if REFERENCE_PATTERN.search(text):
        return "translated_source"
    return "unknown"


def split_text(text: str, chunk_size: int = 1100, overlap: int = 140) -> list[str]:
    if chunk_size < 200 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Use chunk_size >= 200 and 0 <= overlap < chunk_size.")
    paragraphs = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        while len(para) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            cut = para.rfind(" ", 0, chunk_size + 1)
            cut = cut if cut > 0 else chunk_size
            chunks.append(para[:cut].strip())
            para = para[max(0, cut - overlap):].strip()
        candidate = f"{current}\n\n{para}".strip() if current else para
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            chunks.append(current)
            tail = current[-overlap:].strip() if overlap else ""
            current = f"{tail}\n\n{para}".strip()
            if len(current) > chunk_size:  # the overlap plus a paragraph can exceed; preserve the paragraph first
                current = para
        else:
            current = para
    if current:
        chunks.append(current)
    return chunks


def detect_chapter(text: str) -> tuple[str | None, str | None]:
    for line in text.splitlines():
        match = CHAPTER_PATTERN.match(line.strip())
        if match:
            return match.group(1), match.group(2).strip(" .:-–") if match.group(2) else None
    return None, None


def build_chunks(document: dict, chunk_size: int = 1100, overlap: int = 140) -> list[dict]:
    source = document["source"]
    source_id = source["source_id"]
    output, chapter_no, chapter_title = [], None, None
    for page in document["pages"]:
        page_number = int(page["page_number"])
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", page["text"]) if p.strip()]
        groups: list[tuple[str | None, str | None, str]] = []
        current_paragraphs: list[str] = []
        for paragraph in paragraphs:
            detected_no, detected_title = detect_chapter(paragraph)
            if detected_no is not None:
                if current_paragraphs:
                    groups.append((chapter_no, chapter_title, "\n\n".join(current_paragraphs)))
                    current_paragraphs = []
                chapter_no, chapter_title = detected_no, detected_title
            current_paragraphs.append(paragraph)
        if current_paragraphs:
            groups.append((chapter_no, chapter_title, "\n\n".join(current_paragraphs)))
        part = 0
        for group_chapter, group_title, group_text in groups:
            for text in split_text(group_text, chunk_size, overlap):
                part += 1
                verse = VERSE_PATTERN.search(text)
                digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]
                metadata = {
                "source_id": source_id,
                "source_identifier": source.get("source_identifier"),
                "source_sha256": source.get("source_sha256"),
                "source_title": source.get("source_title"),
                "book_name": source.get("book_name"),
                "sthana": source.get("sthana"),
                "chapter_number": group_chapter,
                "chapter_title": group_title,
                "page_number": page_number,
                "pdf_page": page_number,
                "chapter_reference": f"{group_chapter}: {group_title}" if group_chapter else None,
                "verse_number": verse.group(1) if verse else None,
                "edition": source.get("edition"),
                "translator": source.get("translator"),
                "source_file": source.get("source_file"),
                "usage_scope": source.get("usage_scope"),
                "license_note": source.get("license_note"),
                "extraction_method": page.get("extraction_method"),
                "provenance_role": page.get("provenance_role") or classify_provenance(text, page_number=page_number),
            }
                output.append({"id": f"{source_id}-p{page_number}-c{part}-{digest}", "text": text, "metadata": metadata})
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--review-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--chunk-size", type=int, default=1100)
    parser.add_argument("--overlap", type=int, default=140)
    args = parser.parse_args()
    try:
        validate_review(args.input, args.review_manifest)
        document = json.loads(args.input.read_text(encoding="utf-8"))
        chunks = build_chunks(document, args.chunk_size, args.overlap)
    except Exception as exc:
        parser.exit(2, f"Chunking blocked/failed: {exc}\n")
    output = args.output or args.input.with_name("chunks.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Created {len(chunks)} chunks from reviewed extraction: {output}")


if __name__ == "__main__":
    main()
