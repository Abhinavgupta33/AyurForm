# Privacy-safe RAG diagnostics

Implemented structured server-side diagnostics around Ollama generation, JSON parsing, schema/reference validation and safety filtering.

## Instrumentation

- Correlation IDs are generated per pipeline analysis.
- Logs include pipeline stage, exception type, HTTP status, elapsed milliseconds, response length and sanitized response shape.
- Retrieved passage counts and internal `P1`-style IDs are logged.
- Missing schema fields, invalid generated passage IDs and unsafe-advice rejection categories are logged.
- Full prompts, symptom descriptions, cookies, passwords, tokens and unrestricted model output are never logged.
- Streamlit’s existing generic user-facing error remains unchanged.

## Files changed

- `utils/diagnostics.py`
- `models/llm.py`
- `rag/pipeline.py`
- `tests/test_diagnostics.py`

## Verification

Focused diagnostics, Ollama and pipeline tests: **12 passed**.

Run the complete suite with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
