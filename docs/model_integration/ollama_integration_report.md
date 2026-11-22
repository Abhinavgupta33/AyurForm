# Ollama AyurParam integration

The local Ollama adapter is configured for the installed AyurParam GGUF. The Dravya research service uses this adapter with its own structured JSON schema and continues to use the shared BGE/ChromaDB retrieval and validation path.

## Configuration

For a local `.env`, use the following values. Keep `AYURSUTRA_LLM_MODE` and `LLM_PROVIDER` aligned because an explicit mode takes precedence:

```text
AYURSUTRA_LLM_MODE=ollama
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M
OLLAMA_TIMEOUT_SECONDS=180
OLLAMA_TEMPERATURE=0.2
AYURSUTRA_EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
AYURSUTRA_KNOWLEDGE_MODE=development
```

`AYURSUTRA_KNOWLEDGE_MODE=development` selects the isolated development ChromaDB corpus for local evaluation. It is not production-approved source material. Production mode continues to apply the existing production scope and rights filters. `mock` remains available only when explicitly selected; the application does not fall back to it if Ollama fails. The adapter posts system/user messages to `/api/chat`, requests a non-streaming response, and maps unavailable, missing-model, timeout and malformed responses to controlled `OllamaError` messages.

## Files changed

- `config.py`: provider, Ollama URL/model, timeout and temperature settings.
- `models/llm.py`: `OllamaLLM` adapter and controlled error type.
- `ayurform_dravya_research.py`: structured Dravya profile generation through the same `OllamaLLM` adapter, with the profile schema and existing evidence checks.
- `frontend/pages/ayurform_pages.py`: configured model status and inference errors in Dravya Explorer.
- `tests/test_ollama_llm.py`: HTTP-mocked adapter tests, including forwarding a task-specific schema.

## Local commands

PowerShell:

```powershell
ollama serve
ollama list
Copy-Item .env.example .env  # only for a fresh local setup; preserve existing secrets in an existing .env
# Confirm the model is listed before starting the app:
ollama show hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M
uvicorn auth_api:app --host 127.0.0.1 --port 8000
# In a second terminal:
uvicorn ayurform_api:app --host 127.0.0.1 --port 8002
# In a third terminal:
streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

The example file contains placeholder auth/database values: fill those locally and never commit `.env`. For the Dravya test, use the Development knowledge mode so the isolated development collection is selected; resulting profiles remain development-only.

Switch back explicitly:

```powershell
$env:LLM_PROVIDER=""
$env:AYURSUTRA_LLM_MODE="mock"
streamlit run app.py
```

An HTTP smoke test (after Ollama is running) is:

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/chat -Method Post -ContentType 'application/json' -Body ('{"model":"hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M","messages":[{"role":"user","content":"Reply with the word OK."}],"stream":false}' )
```

## Verification

The local Ollama `/api/tags` response listed `hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M` with model ID prefix `b921b960e856`. Live inspection of `/api/chat` showed that Ollama accepted the structured-output request, but the model did not reliably satisfy the profile contract:

- Initial response: HTTP 200, `done_reason=length`, `eval_count=1200`; JSON parsing failed (unterminated string at line 15, column 63).
- Retry: HTTP 200, `done_reason=stop`, `eval_count=1266`; valid JSON with all top-level fields and 11 claims, but repeated Dravya fields. The validator rejected the duplicate fields. Citation values were constrained to the supplied `P1`/`P2` IDs.
- The retrieved eligible passages were development IDs `charaka_vanloon_volume1_dev-p542-c2-8b3a864bf6` (page 542, passage discusses Pippali) and `charaka_vanloon_volume1_dev-p19-c1-d9d1203a55` (page 19, general definitions of Samavaya/Karma). Neither passage names Ashwagandha.
- A field-by-field live trial returned parseable outputs and only prompt-local IDs, but generated candidate content not supported by those excerpts. Those claims were not accepted as evidence-backed.

The current service uses a schema-constrained single-field extraction strategy with passage-ID enums and a conservative subject-name evidence gate. For this corpus/query it abstains because no eligible retrieved passage names Ashwagandha. This is the correct fail-closed result; successful AyurParam-backed profile generation is **not verified**. No model-generated claims from the failed trials were saved or displayed. Automated tests cover successful adapter payloads, custom and passage-constrained schemas, field retries, timeout, missing model, malformed output, citation rejection, and subject-name abstention. No tests download model weights.

## Limitations

Ollama must be installed and the model must already be available locally. The adapter does not fall back to another provider. Prompt JSON validation and existing safety checks remain in `rag.pipeline`; model-generated output is not considered valid until those checks pass.
