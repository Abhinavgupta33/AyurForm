# Diagnostic lifecycle logging

Implemented complete privacy-safe lifecycle events without changing retrieval behavior, prompts, thresholds, model settings, authentication or UI.

Events now include one correlation ID across start, retrieval, generation/validation and final outcome. Retrieval records passage and provenance counts; validation records schema, citation, provenance and safety outcomes; retries and technical failures are recorded; every terminal path emits `grounded_answer`, `abstention` or `technical_failure`.

Files changed:

- `rag/pipeline.py`
- `tests/test_lifecycle_logging.py`
- This report.

Tests: focused lifecycle tests **8 passed**; full suite **76 passed**.
