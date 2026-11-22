# Charaka Samhita Volume I - development ingestion report

Run date: 2026-11-17  
Usage scope: **development_only**  
Source: `D:\Downloads\Charaka-Samhita-Acharya-Charaka.pdf`

This run used an isolated development corpus. It did not modify the production ChromaDB collection, SQLite, authentication, frontend, or the original PDF. Copyright permission remains unverified.

## Development isolation

| Item | Value |
|---|---|
| Development persistence directory | `data/dev_chroma/` |
| Development collection | `charaka_vanloon_dev` |
| Production persistence directory | `vectorstore/` (not written) |
| Production collection count after run | 0 |
| Source registry | `data/dev_metadata/development_source_registry.json` |
| Registry scope | `development_only` |
| Source SHA-256 | `b2b22f11e22f4c4e4d62bdf72418320269324123b7ad481920aba8a61e58d23c` |

The development registry records the source as an edited English handbook with mixed source/editorial content. Its rights status is explicitly unverified and its review status is not production-approved. The production admission validator therefore cannot treat this registry entry as approved production material.

## Extraction

The existing PyMuPDF extraction pipeline was used with OCR disabled (`ocr="never"`).

| Metric | Result |
|---|---:|
| PDF page count | 621 |
| Extracted page records | 621 |
| Digital-text pages | 621 |
| OCR pages | 0 |
| Empty pages | 0 (page records contain separators/page numbers) |
| Extracted characters | 1,053,042 |
| Unusually short pages | 7: 4, 6, 128, 198, 439, 511, 536 |

No text was silently discarded. Short pages remain in the page-preserving extraction artifact and are excluded from ordinary semantic chunks only through their naturally tiny chunk records.

## Chunking

The existing deterministic chunker produced stable IDs and preserved page and chapter metadata.

| Metric | Result |
|---|---:|
| Chunk count | 1,555 |
| Minimum chunk length | 1 character |
| Maximum chunk length | 1,100 characters |
| Mean chunk length | 731.6 characters |
| Median chunk length | 836 characters |
| Overlap setting | 140 characters |

Each record preserves `source_id`, `source_title`, `source_sha256`, `page_number`, `pdf_page`, `chapter_number`, `chapter_title`, `chapter_reference` when detectable, `verse_number` when detectable, `provenance_role`, `usage_scope`, extraction method, and source credits/notes.

## Conservative provenance classification

Classification is intentionally conservative. Explicit editorial/table signals are labeled; text without sufficient evidence remains `unknown` rather than being guessed as source translation.

| Provenance role | Chunks |
|---|---:|
| `translated_source` | 490 |
| `editor_note` | 730 |
| `table` | 7 |
| `translator_note` | 0 |
| `editorial_commentary` | 0 |
| `unknown` | 328 |

The development index allows `unknown` provenance for experimentation. The production index gate still rejects unknown provenance and requires an approved production source registry entry.

## Embeddings and ChromaDB

| Item | Result |
|---|---|
| Embedding model | `BAAI/bge-base-en-v1.5` |
| Embedding dimension | 768 |
| Development records written | 1,555 |
| Collection metadata | cosine distance; BGE model recorded |
| Retrieval smoke test | Passed; first chunk retrieved from the written collection |
| Idempotent write behavior | Stable chunk IDs and source-scoped upsert/stale deletion retained |

Embeddings were generated only for the development collection. No production embeddings were generated or written.

## Artifacts

- Page extraction: `data/dev_extracted/charaka_vanloon_volume1_dev_pages.json`
- Review manifest: `data/dev_extracted/review_approval.json`
- Development chunks: `data/dev_extracted/charaka_vanloon_volume1_dev_chunks.json`
- Development registry: `data/dev_metadata/development_source_registry.json`
- Development ChromaDB: `data/dev_chroma/`

## Limitations

- The source is an edited handbook with interleaved editorial material; classification is heuristic and must not be presented as scholarly provenance.
- Rights and permission were not established.
- Unknown and editor-labeled chunks are present in the development collection for pipeline testing only.
- This milestone does not implement retrieval behavior or AyurParam inference.
