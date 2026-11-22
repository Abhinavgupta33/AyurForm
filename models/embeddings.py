"""Lazy BGE embedding model wrapper."""

from __future__ import annotations

import math

from sentence_transformers import SentenceTransformer

from config import EMBEDDING_MODEL_NAME


class BGEEmbeddings:
    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME, device: str = "cpu") -> None:
        self.model_name = model_name
        self.model = SentenceTransformer(model_name, device=device)
        self.dimension = self.model.get_sentence_embedding_dimension()
        if not isinstance(self.dimension, int) or self.dimension < 1:
            raise RuntimeError(f"Embedding model {model_name!r} did not report a valid output dimension.")

    def _encode(self, texts: str | list[str]) -> list[float] | list[list[float]]:
        vectors = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        rows = vectors.tolist() if hasattr(vectors, "tolist") else vectors
        if isinstance(texts, str):
            rows = rows
            vector = rows
            if len(vector) != self.dimension:
                raise RuntimeError(f"Expected {self.dimension}-dimensional embeddings, received {len(vector)}.")
            if not all(math.isfinite(float(value)) for value in vector):
                raise RuntimeError("Embedding model returned a non-finite value.")
            return vector
        if len(rows) != len(texts) or any(len(row) != self.dimension for row in rows):
            raise RuntimeError(f"Embedding model returned invalid dimensions; expected {len(texts)} x {self.dimension}.")
        if not all(math.isfinite(float(value)) for row in rows for value in row):
            raise RuntimeError("Embedding model returned a non-finite value.")
        return rows

    def embed_query(self, text: str) -> list[float]:
        return self._encode(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts)
