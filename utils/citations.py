"""Format citations using only provenance stored during ingestion."""


def format_reference(metadata: dict) -> str:
    parts = [metadata.get("source_title") or metadata.get("book_name") or "Source title unavailable"]
    if metadata.get("sthana"):
        parts.append(str(metadata["sthana"]))
    chapter = metadata.get("chapter_number")
    title = metadata.get("chapter_title")
    if chapter or title:
        value = f"Chapter {chapter}" if chapter else "Chapter"
        if title:
            value += f": {title}"
        parts.append(value)
    if metadata.get("verse_number"):
        parts.append(f"Verse {metadata['verse_number']}")
    if metadata.get("page_number"):
        parts.append(f"PDF page {metadata['page_number']}")
    if metadata.get("edition"):
        parts.append(str(metadata["edition"]))
    if metadata.get("translator"):
        parts.append(f"trans. {metadata['translator']}")
    return " · ".join(parts)


def validate_passage_ids(values, passages: list[dict]) -> list[str]:
    allowed = {f"P{i}" for i in range(1, len(passages) + 1)}
    return [value for value in values if value in allowed]
