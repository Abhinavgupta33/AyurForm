# Development ChromaDB connection report

## Root cause

The application retrieval path used `VECTORSTORE_DIR` (`data/../vectorstore`) and `CHROMA_COLLECTION` (`charaka_samhita`) unconditionally. The development ingestion was stored separately at `data/dev_chroma/` in `charaka_vanloon_dev`, so the application was correctly seeing an empty/uninitialized production collection and the dashboard reported zero passages.

The existing `retrieval/dev_retriever.py` already had strict development-only protections, but the application’s normal `rag.retriever` was not connected to it.

## Fix

Added explicit `AYURSUTRA_KNOWLEDGE_MODE` configuration:

```text
AYURSUTRA_KNOWLEDGE_MODE=development
```

Development mode selects only `data/dev_chroma/charaka_vanloon_dev`; production remains the default and continues selecting `vectorstore/charaka_samhita`. Development retrieval results receive `usage_scope=development_only`, and the sidebar labels the selected corpus as development-only.

The BGE model remains `BAAI/bge-base-en-v1.5`, matching the development collection’s recorded embedding model. No records were copied, re-ingested, or modified.

## Verification

Added tests covering development scope metadata, collection separation, and configuration safety. Full production retrieval behavior remains unchanged when `AYURSUTRA_KNOWLEDGE_MODE` is not set.

Run:

```powershell
$env:AYURSUTRA_KNOWLEDGE_MODE="development"
pytest -q
```

Use `AYURSUTRA_KNOWLEDGE_MODE=production` (or unset it) to return to the production collection.
