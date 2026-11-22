# Ollama structured-output improvement

Implemented schema-constrained generation for AyurParam through Ollama.

## Changes

- Added a single JSON Schema matching the application response contract, including nested concept fields and supporting passage IDs.
- Sent that schema as `/api/chat` `format` for both initial and retry requests (the same adapter path is used for both).
- Removed the unnecessary `<assistant>` delimiter from the generated prompt.
- Kept `num_predict=350` and the configured temperature unchanged. The budget is retained pending live measurement; increasing it without evidence could increase latency and output risk.
- Preserved application parsing, typed validation, citation-ID, provenance and safety checks.

## Files changed

- `models/llm.py`
- `tests/test_ollama_llm.py`
- `tests/test_response_schema.py`
- This report.

## Verification

Focused and full test suites were run. Live reliability against the installed Ollama model is not claimed by this code-only change; a live smoke test remains required.
