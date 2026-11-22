# RAG reliability fixes

Implemented three targeted fixes without changing UI, authentication, ingestion, embeddings, model weights or ChromaDB records.

## Changes

- Diagnostics initialization is explicitly invoked by both `app.py` and `auth_api.py`; initialization remains idempotent and development-only.
- AyurParam responses now require the complete structured-answer contract with type validation. Missing/wrong fields raise a schema failure and use the existing Ollama retry. A failed retry returns a controlled validation-failure result, never a successful empty answer.
- `evidence_sufficient` now requires at least one `translated_source` passage. Editorial, unknown and other provenance remain visible as context but cannot alone support a classical-text claim.

## Files changed

- `app.py`
- `auth_api.py`
- `models/llm.py`
- `rag/pipeline.py`
- `tests/test_recurrent_reference_validation.py`
- `tests/test_provenance_sufficiency.py`
- `tests/test_diagnostics.py`
- This report.

## Tests

Full suite: **74 passed** (6 existing dependency deprecation warnings).

Coverage includes schema/type failures, strict retry behavior, invalid citation IDs, diagnostics initialization, editorial-only/unknown evidence, translated-source evidence and mixed provenance behavior.
