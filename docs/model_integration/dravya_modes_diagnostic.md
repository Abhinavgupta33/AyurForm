# Dravya RAG and Approved Search Diagnostic

Date: 2026-11-22  
Repository: `D:\Project\ayursutra-ai`  
Scope: read-only diagnosis; no application code, database rows, ChromaDB records, or environment variables were changed.

## Findings

### Source-grounded RAG

The reported Pippali no-results condition did **not** reproduce against the running application configuration.

- The running Streamlit process is using `AYURSUTRA_KNOWLEDGE_MODE=development`.
- `config.py` resolves that mode to `data/dev_chroma/` and `charaka_vanloon_dev` (`ACTIVE_VECTORSTORE_DIR` / `ACTIVE_CHROMA_COLLECTION`).
- The active collection exists and contains **1,555** records. Its metadata records `BAAI/bge-base-en-v1.5`.
- The production path `vectorstore/`, collection `charaka_samhita`, also exists but contains **0** records. Selecting production mode would therefore produce no retrieval results from the current production collection.
- BGE loaded successfully. The model and query vector both reported **768 dimensions**.
- `rag.retriever.PassageRetriever.retrieve()` queried the development collection with the same embedding model. `ayurform_research.select_evidence()` then retained `translated_source` passages. `build_dravya_answer()` additionally enforces the configured maximum distance and requires the passage text to mention the requested name. In development mode it does not apply the production-rights filter; UI labels the returned evidence as development-only and rights-pending.

The exact passage previously identified is present:

| Rank | Passage ID | Distance | Similarity (`1 - distance`) | Provenance | Page | Match to Pippali |
|---:|---|---:|---:|---|---:|---|
| 1 | `charaka_vanloon_volume1_dev-p542-c2-8b3a864bf6` | 0.266833 | 0.733167 | translated_source | 542 | Yes |
| 2 | `charaka_vanloon_volume1_dev-p609-c1-8175b2fd5d` | 0.287172 | 0.712828 | editor_note | 609 | Yes, mentioned as an ingredient |
| 3 | `charaka_vanloon_volume1_dev-p77-c3-41f9820dd9` | 0.300381 | 0.699619 | editor_note | 77 | Yes, in a group list |
| 4 | `charaka_vanloon_volume1_dev-p548-c2-036fc27aef` | 0.301613 | 0.698387 | editor_note | 548 | Yes, in a group list |
| 5 | `charaka_vanloon_volume1_dev-p583-c1-e9c31caea1` | 0.302749 | 0.697251 | translated_source | 583 | No; about Vatsaka |

The first passage metadata identifies the source as *Charaka Samhita - Handbook on Ayurveda Volume I*, chapter reference `II: “The Flowered Person”`, page 542, provenance `translated_source`, usage scope `development_only`, and a license note saying permission is not established. The displayed chapter-title encoding is garbled in the stored metadata.

Concise retrieved excerpt from that development-only passage:

> “3 substances to not use excessively: pippali, alkali, and salt -Vi1#15 Pippali (long pepper): Rasa: pungent. Vipaka: sweet.”

`select_evidence()` reduces the top results to two translated-source passages (pages 542 and 583). The subsequent exact-subject check excludes the Vatsaka passage, leaving the page-542 passage as the sole eligible evidence for this Pippali query. Its distance, **0.266833**, is below `AYURSUTRA_MAX_COSINE_DISTANCE=0.85`; the threshold is not the cause of empty retrieval.

An actual call through `build_dravya_answer("Pippali", OllamaLLM(), top_k=8)` completed as `grounded`, with one evidence passage (`...p542...`) and citation ID `P1`. The validated answer had 809 characters. The Streamlit renderer in `frontend/pages/ayurform_pages.py` displays the answer and a separate expandable retrieved-evidence section. No RAG no-results failure was reproduced in this run.

**RAG root cause:** no current retrieval defect was found. The known empty production collection is a plausible cause if an earlier process was running with production mode, but the live process inspected for this report is in development mode. In the current configuration, RAG retrieves relevant evidence and generates a grounded answer. Editor notes are excluded from source-grounded generation by `ayurform_research.select_evidence()`.

### Approved-record search

The search returned an empty result because the connected structured database contains no scholarly rows, not because the request or response parsing is broken.

- The running AyurForm API process is on port 8002, has working directory `D:\Project\ayursutra-ai`, and reports `sqlite_development`, connected.
- It has no `AYURFORM_DB_PATH` process override. `ayurform_store.DB_PATH` therefore resolves to `D:\Project\ayursutra-ai\ayurform_dev.db`.
- The Streamlit process uses the same project working directory and `AYURFORM_API_URL=http://localhost:8002`. The API process loads the project `.env` from that directory. The API response and direct local database counts agree.
- API health: **HTTP 200**, database connected.
- `GET http://localhost:8002/api/dravya?search=Pippali&limit=50`: **HTTP 200**, response keys `items` and `development_only`, `items=[]`. The same request to `127.0.0.1:8002` also returned HTTP 200 and no items.
- The UI calls this route with `httpx.get()` in the Streamlit server process and parses `response.json().get("items", [])`; request and response contracts match.

| Table | Total rows | Approved | Pending/rejected |
|---|---:|---:|---:|
| sources | 0 | 0 | 0 |
| source_passages | 0 | 0 | 0 |
| dravya | 0 | 0 | 0 |
| dravya_synonyms | 0 | — | — |
| dravya_attributes | 0 | 0 | 0 |

Records excluded for production-scope or rights restrictions: **0**, because there are no records in this database to classify. The public Dravya query additionally requires an approved Dravya plus approved translated-source attribute/passage and an approved production source with verified, licensed, or public-domain rights. That gate is operating as designed.

**Approved-search root cause:** the empty state is expected. The active SQLite database has zero Dravya records, so Pippali cannot match. It is not an API error or frontend parsing failure.

## Runtime paths and responsible code

- Configuration and dev/production vector selection: `config.py` (`KNOWLEDGE_MODE`, `ACTIVE_VECTORSTORE_DIR`, `ACTIVE_CHROMA_COLLECTION`).
- Vector query and BGE embedding: `rag/retriever.py` (`PassageRetriever.retrieve`).
- Translated-source filtering: `ayurform_research.py` (`select_evidence`).
- Pippali mention, relevance, production-rights filtering, and answer call: `ayurform_dravya_research.py` (`build_dravya_answer`).
- Dravya approved search route and JSON shape: `ayurform_api.py` (`list_entity`).
- Approved-only query and production evidence/rights gate: `ayurform_store.py` (`rows`, `_sqlite_public_dravya_details`).
- UI mode dispatch, approved API request, error/empty state and RAG evidence renderer: `frontend/pages/ayurform_pages.py` (`render_ayurform_page`).

RAG is invoked locally by the Streamlit page through `build_dravya_answer`; it does not call the AyurForm FastAPI endpoint. FastAPI is used for approved-record search.

## Minimal recommendations

1. No RAG fix is indicated for the live development configuration. If users see empty RAG results, capture the running process’s `KNOWLEDGE_MODE`, active collection, collection count, and the `build_dravya_answer` outcome before changing thresholds or filters. Restart Streamlit after changing its environment so import-time configuration refreshes.
2. Keep the empty approved-search state. Populate it only after an appropriately licensed/public-domain/permissioned source and its evidence are registered, and reviewed Dravya records are entered through the pending workflow. Do not use the rights-pending Van Loon development corpus for production records.
3. Do not change the distance cutoff or provenance rules based on this run: the relevant page-542 passage is returned well within the configured distance limit and its provenance is `translated_source`.

## Tests

- Focused: **47 passed**, 1 warning.
- Full suite: **153 passed, 2 skipped**, 6 warnings.
- The two PostgreSQL integration tests are skipped unless `AYURFORM_TEST_DATABASE_URL` is configured. This diagnostic used the running SQLite development API and did not modify database or vector data.
