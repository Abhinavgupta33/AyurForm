# Generated reference validation debug report

## Reproduction

Using the configured development collection and local Ollama provider, the query `burning in stomach and sour belching` completed retrieval and generation, then failed during validation with:

```text
ValueError: AyurParam returned no structured JSON response.
  models/llm.py:118 in parse_structured_response
  models/llm.py:133 in validate_generation
  rag/pipeline.py:97 in get_ayurvedic_response
```

The raw Ollama response was prose, not a JSON object. It included unsupported causal claims and treatment/medication advice. It contained no `possible_concepts`, no `supporting_passage_ids`, and therefore no generated references to compare with retrieved references.

## Root cause

This is a generation-format failure, not a citation metadata or reference-format failure. The existing validator correctly rejected the response rather than accepting fabricated references. Retrieved references were formatted from indexed metadata by `format_reference` (for example, `Charaka Samhita · PDF page 8` when only those fields exist); they were never reached by generated-reference validation because parsing failed first.

The local Q4 model did not reliably follow the prompt’s “ONLY valid JSON” instruction. The smallest safe correction is to request Ollama’s structured JSON response using the `/api/chat` `format: "json"` option. Validation remains mandatory and still rejects malformed JSON, unsupported passage IDs, and unsafe advice.

## Files changed

- `models/llm.py`: request Ollama JSON output.
- `tests/test_ollama_llm.py`: assert the JSON-format request.
- `tests/test_reference_validation_debug.py`: regression test proving prose is rejected.
- This report.

No source records, provenance rules, authentication, UI, ingestion, embeddings or ChromaDB data were changed.

## Verification

The failure was reproduced against the local configuration. Automated tests cover the correction and the existing validation path. After the change, a fresh live request completed with `mode=ollama`, five retrieved passages, and a non-empty validated evidence summary. The model response is now accepted only after the existing JSON, passage-ID and safety validation.
