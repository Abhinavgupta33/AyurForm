# Citation and provenance integrity update

Implemented targeted validation and diagnostics improvements.

## Behavior changes

- Invalid generated citation IDs now reject the entire concept; IDs are never silently filtered.
- Concepts citing any non-`translated_source` passage are suppressed and logged as provenance-invalid.
- Prompt construction returns the exact passage subset included in the model context; validation uses that same subset.
- Nested concept objects and field types are strictly validated.
- Diagnostics now record JSON parse shape, concept counts, completion metadata and token-limit indicators without private content.

Files changed: `models/llm.py`, `rag/pipeline.py`, `utils/diagnostics.py`, related tests.

Full suite: **81 passed**.
