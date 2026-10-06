"""ChromaDB-backed vector store for policy chunks."""

from __future__ import annotations

from dataclasses import dataclass

import chromadb

from bankrag.chunking import Chunk
from bankrag.config import Settings
from bankrag.embeddings import Embedder


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: Chunk
    score: float  # cosine similarity, higher is better


class VectorStore:
    def __init__(self, settings: Settings, embedder: Embedder, persistent: bool = True):
        self.embedder = embedder
        if persistent:
            self._client = chromadb.PersistentClient(path=str(settings.chroma_dir))
        else:
            self._client = chromadb.EphemeralClient()
        # One collection per embedder, so switching backends never mixes vectors.
        safe_name = "".join(c if c.isalnum() else "-" for c in embedder.name)[-50:]
        self._collection = self._client.get_or_create_collection(
            name=f"arya-policies-{safe_name}".strip("-"),
            metadata={"hnsw:space": "cosine"},
            embedding_function=None,
        )

    def count(self) -> int:
        return self._collection.count()

    def index(self, chunks: list[Chunk]) -> None:
        existing = self._collection.get()["ids"]
        if existing:
            self._collection.delete(ids=existing)
        self._collection.add(
            ids=[c.chunk_id for c in chunks],
            embeddings=self.embedder.embed([c.as_context() for c in chunks]),
            documents=[c.text for c in chunks],
            metadatas=[
                {"doc_id": c.doc_id, "title": c.title, "section": c.section, "source": c.source}
                for c in chunks
            ],
        )

    def search(self, query: str, top_k: int) -> list[RetrievedChunk]:
        result = self._collection.query(
            query_embeddings=self.embedder.embed([query]),
            n_results=min(top_k, self.count()),
        )
        hits = []
        for chunk_id, text, meta, distance in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
        ):
            chunk = Chunk(
                chunk_id=chunk_id,
                doc_id=meta["doc_id"],
                title=meta["title"],
                section=meta["section"],
                text=text,
                source=meta["source"],
            )
            hits.append(RetrievedChunk(chunk=chunk, score=1.0 - distance))
        return hits
