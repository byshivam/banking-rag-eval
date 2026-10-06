"""Embedding backends.

- `sentence-transformers`: real semantic embeddings, runs locally and free.
- `hash`: a tiny bag-of-words hashing embedder with no downloads. It is only
  lexical, so it is used for fast offline unit tests in CI — never for real evals.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from bankrag.config import Settings


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashingEmbedder:
    name = "hash"

    def __init__(self, dim: int = 512):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vec = [0.0] * self.dim
            for token in re.findall(r"[a-z0-9₹]+", text.lower()):
                bucket = int(hashlib.md5(token.encode()).hexdigest(), 16) % self.dim
                vec[bucket] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.name = model_name
        self._model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, normalize_embeddings=True).tolist()


def get_embedder(settings: Settings) -> Embedder:
    if settings.embedding_backend == "hash":
        return HashingEmbedder()
    if settings.embedding_backend == "sentence-transformers":
        return SentenceTransformerEmbedder(settings.embedding_model)
    raise ValueError(f"Unknown EMBEDDING_BACKEND: {settings.embedding_backend!r}")
