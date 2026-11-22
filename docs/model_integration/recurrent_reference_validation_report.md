# Recurrent reference validation report

## Exact exception

The failing Streamlit workflow reproduced as:

```text
ValueError: AyurParam returned no structured JSON response.
  models/llm.py:126 in parse_structured_response
  models/llm.py:141 in validate_generation
  rag/pipeline.py:97 in get_ayurvedic_response
```

The failure is intermittent and input/model-output dependent. Retrieval completed with five passages from `charaka_vanloon_dev`; the model sometimes returned plain prose despite Ollama JSON mode. A separate response was JSON-shaped but contained source metadata fields rather than the required `possible_concepts`/`supporting_passage_ids` schema. Those fields were not treated as citations.

## Root cause and safety behavior

This is local-model output non-compliance, not a missing ChromaDB reference or metadata formatting defect. Retrieved passage IDs are internal `P1` through `P5`. The validator accepts only those IDs and never accepts generated source IDs, page numbers, or arbitrary metadata as citations. Prose and malformed JSON remain rejected.

The smallest safe correction adds one Ollama-only retry with an explicit JSON-only instruction after a validation parse/type failure. The retried response must still pass the unchanged JSON, passage-ID and unsafe-advice validation. Other providers are not retried or altered.

## Verification

Focused tests: **11 passed**. A live development request after the correction completed with `mode=ollama`, five retrieved passages and a validated evidence summary. No ChromaDB records, ingestion, authentication or UI styling changed.

## Files changed

- `rag/pipeline.py`
- `models/llm.py`
- `tests/test_recurrent_reference_validation.py`
- `tests/test_ollama_llm.py`
- `docs/model_integration/recurrent_reference_validation_report.md`
