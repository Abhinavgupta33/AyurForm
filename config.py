"""Central configuration for AyurSutra AI."""

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    pass

DATA_DIR = ROOT_DIR / "data"
PDF_DIR = DATA_DIR / "source_pdfs"
EXTRACTED_DIR = DATA_DIR / "extracted_text"
METADATA_DIR = DATA_DIR / "metadata"
VECTORSTORE_DIR = ROOT_DIR / "vectorstore"
DEV_VECTORSTORE_DIR = DATA_DIR / "dev_chroma"
DATABASE_URL = os.getenv("DATABASE_URL", "")
AYURFORM_DB_FALLBACK = os.getenv("AYURFORM_DB_FALLBACK", "").strip().lower() == "sqlite"

EMBEDDING_MODEL_NAME = os.getenv("AYURSUTRA_EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").strip().lower()
# An explicitly supplied AYURSUTRA_LLM_MODE is authoritative (notably mock).
# With no explicit mode, LLM_PROVIDER selects the backend; otherwise retain the
# historical mock default.
_configured_mode = os.getenv("AYURSUTRA_LLM_MODE", "").strip().lower()
LLM_MODE = _configured_mode or ("mock" if not LLM_PROVIDER else "")
LLM_MODEL_NAME = os.getenv("AYURSUTRA_LLM_MODEL", "bharatgenai/AyurParam")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
OLLAMA_CONNECT_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_CONNECT_TIMEOUT_SECONDS", "10"))
OLLAMA_GENERATION_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_GENERATION_TIMEOUT_SECONDS", "300"))
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))
AYURSUTRA_RESEARCH_NUM_PREDICT = int(os.getenv("AYURSUTRA_RESEARCH_NUM_PREDICT", "800"))
AYURSUTRA_RESEARCH_NUM_CTX = int(os.getenv("AYURSUTRA_RESEARCH_NUM_CTX", "4096"))
AYURSUTRA_RESEARCH_CONTEXT_MAX_CHARS = int(os.getenv("AYURSUTRA_RESEARCH_CONTEXT_MAX_CHARS", "6500"))
TOP_K = int(os.getenv("AYURSUTRA_TOP_K", "5"))
MAX_COSINE_DISTANCE = float(os.getenv("AYURSUTRA_MAX_COSINE_DISTANCE", "0.85"))
CHROMA_COLLECTION = os.getenv("AYURSUTRA_CHROMA_COLLECTION", "charaka_samhita")
KNOWLEDGE_MODE = os.getenv("AYURSUTRA_KNOWLEDGE_MODE", "production").strip().lower()
if KNOWLEDGE_MODE not in {"production", "development"}:
    raise ValueError("AYURSUTRA_KNOWLEDGE_MODE must be 'production' or 'development'.")
ACTIVE_VECTORSTORE_DIR = DEV_VECTORSTORE_DIR if KNOWLEDGE_MODE == "development" else VECTORSTORE_DIR
ACTIVE_CHROMA_COLLECTION = "charaka_vanloon_dev" if KNOWLEDGE_MODE == "development" else CHROMA_COLLECTION

DISCLAIMER = (
    "For education only. This tool does not diagnose, treat, or prevent disease. "
    "Symptoms can have many causes. Classical textual concepts are not modern clinical evidence. "
    "Consult a qualified healthcare professional for personal medical advice."
)
