"""Privacy-safe diagnostics for model and retrieval workflows."""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import uuid

LOGGER = logging.getLogger("ayursutra.rag")
EXPECTED_FIELDS = ("extracted_symptoms", "possible_concepts", "evidence_summary", "limitations")
_FILE_HANDLER_MARKER = "_ayursutra_diagnostics_file"


class RedactionFilter(logging.Filter):
    """Defensive redaction for accidental credential-like log values."""
    _patterns = (
        (re.compile(r"(?i)(password|token|cookie|authorization)(\s*[:=]\s*)[^\s,;]+"), r"\1\2[REDACTED]"),
    )

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern, replacement in self._patterns:
            message = pattern.sub(replacement, message)
        record.msg, record.args = message, ()
        return True


def configure_file_logging(*, log_dir: str | Path | None = None, development: bool | None = None) -> bool:
    """Install one rotating development file handler; leave production unchanged."""
    enabled = development if development is not None else os.getenv("AYURSUTRA_ENV", "").casefold() == "development"
    if not enabled:
        return False
    directory = Path(log_dir) if log_dir is not None else Path(__file__).resolve().parents[1] / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    if any(getattr(handler, _FILE_HANDLER_MARKER, False) for handler in LOGGER.handlers):
        return True
    handler = RotatingFileHandler(directory / "rag_diagnostics.log", maxBytes=5 * 1024 * 1024,
                                  backupCount=3, encoding="utf-8")
    setattr(handler, _FILE_HANDLER_MARKER, True)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(RedactionFilter())
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    return True


configure_file_logging()


def correlation_id(value: str | None = None) -> str:
    return value or uuid.uuid4().hex[:12]


def response_shape(value: str) -> dict:
    shape = {"response_length": len(value), "has_json_object": "{" in value and "}" in value}
    try:
        import json
        parsed = json.loads(value)
        shape["json_parse"] = "success"
        shape["root_type"] = type(parsed).__name__
        if isinstance(parsed, dict):
            shape["missing_fields"] = [f for f in ("extracted_symptoms", "possible_concepts", "evidence_summary", "limitations") if f not in parsed]
            shape["concept_count"] = len(parsed.get("possible_concepts", [])) if isinstance(parsed.get("possible_concepts"), list) else None
    except Exception:
        shape["json_parse"] = "failure"
        shape["root_type"] = "unknown"
    return shape
