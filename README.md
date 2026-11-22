# AyurSutra AI

**Shabda-to-Ayurveda: educational symptom mapping and classical passage retrieval.** This Streamlit application searches a locally indexed authorized English translation of Charaka Samhita and can pass retrieved excerpts to the official BharatGen AyurParam model. It does not diagnose or prescribe.

## Current status

- The app, local PDF ingestion stages, ChromaDB retrieval, AyurParam Transformers adapter, and safety/citation checks are implemented.
- No Charaka Samhita PDF was found in the workspace. The repository intentionally contains no book text, sample classical excerpts, or fabricated references. Until you supply an authorized translation and index it, the app will explain that sufficient source evidence was not found.
- Development starts in `mock` mode. Mock mode is labelled, does not generate conceptual associations, and never claims to be AyurParam output.
- AyurParam's official Hugging Face repository is `bharatgenai/AyurParam`; its model card uses Transformers with `trust_remote_code=True`. Review that model's license before use: the model card license metadata and the repository `LICENSE` have conflicted. BharatGen currently recommends 8 GB GPU memory for AyurParam; the checked development PC has 4 GB VRAM.

## Requirements

- Windows 10/11 and Python 3.11+ (the checked machine has Python 3.12.10).
- Network access for the initial Python packages and BGE model download.
- For actual local AyurParam inference, use hardware meeting the model provider's current memory guidance or a rented GPU. A Hugging Face account may be needed to accept model terms. There is no fallback to another LLM.
- Only ingest a Charaka Samhita edition that you are authorized to use. This project keeps source title, rights note, edition, translator, and extracted page numbers with the corpus.

## Windows PowerShell setup

```powershell
cd D:\Project\ayursutra-ai
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

If PyTorch does not detect your NVIDIA GPU, use the official [PyTorch Windows install selector](https://pytorch.org/get-started/locally/) and choose Windows, pip, Python, and the CUDA build suited to your driver. The CUDA number shown by `nvidia-smi` is not itself the wheel selector.

Verify packages and CUDA:

```powershell
python -c "import torch, streamlit, chromadb, fitz, transformers; print('torch', torch.__version__); print('CUDA', torch.cuda.is_available()); print('GPU', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

## Run the website

```powershell
cd D:\Project\ayursutra-ai
\.venv\Scripts\Activate.ps1
streamlit run app.py
```

The embedding model is `BAAI/bge-base-en-v1.5`. With an empty vector store the app does not download BGE and instead returns a clear evidence-insufficient result. The ingestion and query sides use the same `BGEEmbeddings` wrapper and normalized SentenceTransformer encoding.

## Authorized source ingestion (not run yet)

Place the authorized translation at `data\source_pdfs\charaka_english.pdf`. Do not use this example path until you have supplied a source you are permitted to use. Provide only bibliographic metadata confirmed from that source; leave optional fields out if unknown. The rights note records your basis but does not grant rights by itself.

One interactive command runs extraction → a blocking review checkpoint → chunking → BGE embeddings → ChromaDB upsert → source-scoped retrieval verification. It prints the extraction file and quality report, then waits for the reviewer to inspect the JSON in an editor and type the exact hash-bound approval phrase. Any edit after approval invalidates the review. Declining or closing stdin stops before chunking/indexing.

```powershell
python ingestion\run_pipeline.py `
  --pdf data\source_pdfs\charaka_english.pdf `
  --source-id charaka_english `
  --source-title "Title as printed in this translation" `
  --book-name "Charaka Samhita" `
  --edition "Publisher/edition/year, if printed" `
  --translator "Translator/editor, if printed" `
  --license-note "Exact license or permission basis" `
  --authorization "Confirmed authorization basis for local use" `
  --reviewer "Reviewer name or identifier"
```

For scanned pages, `--ocr auto` (default) attempts OCR only on pages with fewer than 40 digital-text characters; `--ocr always` forces OCR and `--ocr never` disables it. OCR is provided by PyMuPDF through the external Tesseract executable. Install Tesseract and the relevant language data (English default) and ensure it is on `PATH`. OCR failures identify the page and stop extraction when no digital text is available. The quality report lists digital/OCR/blank pages, character totals, and pages needing manual inspection.

The auditable separate-stage alternative is: run `extract_text.py` with the same required source metadata flags; inspect/correct `data\extracted_text\<source-id>_pages.json`; run `python ingestion\approve_review.py --input data\extracted_text\<source-id>_pages.json --reviewer "Reviewer identifier"` and enter the exact hash-bound phrase; then run `python ingestion\chunk_text.py --input data\extracted_text\<source-id>_pages.json --review-manifest data\extracted_text\review_approval.json` followed by `python ingestion\create_embeddings.py --chunks data\extracted_text\chunks.json --extraction data\extracted_text\<source-id>_pages.json --review-manifest data\extracted_text\review_approval.json`. Both chunking and indexing reject missing or stale review approvals.

The metadata retained per chunk includes `source_id`, original `source_identifier` (when supplied), source SHA-256, source title, book name, explicit Sthana, chapter number/title only when an explicit heading is detected, original PDF page number, verse marker only when detected, edition, translator, source filename, license note, and extraction method. Missing values are omitted by ChromaDB, never inferred. Chunk ids are deterministic from source id, PDF page, page-local chunk sequence, and content hash. Re-ingestion upserts the same ids, then removes stale records belonging only to that source after all upsert batches succeed; it never clears the collection.

Successful output must report a nonzero `source_records` count and `retrieval_verified: true`, along with the actual retrieved record id and metadata. Confirm independently with the app's indexed-passage count or `python -c "from chromadb import PersistentClient; from config import VECTORSTORE_DIR,CHROMA_COLLECTION; c=PersistentClient(path=str(VECTORSTORE_DIR)).get_collection(CHROMA_COLLECTION); print(c.count())"`. A successful script exit without these checks is not considered a completed ingestion.

## Enable official AyurParam

Set the mode in `.env`:

```text
AYURSUTRA_LLM_MODE=ayurparam
AYURSUTRA_LLM_MODEL=bharatgenai/AyurParam
```

Then follow the official model card's access process and sign in using the Hugging Face CLI if prompted:

```powershell
hf auth login
```

The app uses the official repository through `AutoTokenizer` and `AutoModelForCausalLM` with `trust_remote_code=True`; model loading is lazy and occurs only when there are retrieved passages. Generation is never silently substituted. If loading fails (including GPU memory exhaustion), the interface reports the error. To return to clearly labelled development mode, set `AYURSUTRA_LLM_MODE=mock`.

The model card metadata currently says Apache 2.0, while the model repository's `LICENSE` has stated BharatGen Research License terms. Confirm the operative license with BharatGen before public deployment or commercial use. Public/SaaS model hosting may require written permission under that license.

## Tests and 10-question smoke evaluation

```powershell
python -m pytest -q
python evaluate_samples.py
```

The automated tests use synthetic passages and temporary test databases only; they do not write to the application's real ChromaDB and do not represent classical source content. The 10 sample questions are a smoke test. Without an authorized indexed book, they should all report insufficient evidence; they do not validate AyurParam quality or classical citation correctness. Once authorized source data is indexed, inspect each retrieved reference against that edition.

## Project structure

```text
app.py, config.py, requirements.txt
data/source_pdfs/       # user-provided authorized sources (ignored by git)
data/extracted_text/    # extracted page and chunk JSON (ignored by git)
data/metadata/          # provenance JSON (ignored by git)
vectorstore/            # local ChromaDB files (ignored by git)
ingestion/              # extraction, chunking, embedding/index stages
models/                 # BGE embeddings and official AyurParam adapter
rag/                    # retrieval and grounded response pipeline
utils/                  # citations and safety checks
tests/                  # unit tests and 10 sample questions
```
