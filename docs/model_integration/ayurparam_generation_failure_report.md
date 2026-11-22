# AyurParam generation failure report

## Root cause

The direct Ollama test used a short prompt and succeeded. The real application sent the full grounded prompt with five retrieved passages. The measured prompt was approximately **10,167 characters**, exceeding the practical context budget of the 2.9B GGUF configuration. Ollama returned HTTP **500 Internal Server Error** from `/api/chat` before reference validation or JSON parsing.

Traceback (sanitized):

```text
httpx.HTTPStatusError: Server error '500 Internal Server Error'
  httpx response.raise_for_status()
models.llm.OllamaError: Ollama is unavailable or returned an invalid response.
```

This explains why a short direct `{\"status\":\"success\"}` request worked while the Streamlit workflow failed during generation. The failure occurs before response parsing and before citation validation.

## Correction

`build_prompt` now bounds each passage excerpt to 1,200 characters and the combined context to 6,500 characters. Retrieved passages and their metadata remain unchanged in the result; only the generation context is bounded. JSON enforcement, safety filtering and passage-ID validation remain active. No fallback to Mock is introduced.

## Verification

- Focused generation/validation tests pass.
- Full suite passes after the change.
- The failure was reproduced with the real development collection and Ollama provider; the observed 500 was caused by the oversized application prompt.

## Files changed

- `models/llm.py`
- `tests/test_reference_validation_debug.py`
- This report.
