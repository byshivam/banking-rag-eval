"""Build (or rebuild) the vector index from data/docs.

Usage: python -m bankrag.ingest
"""

from bankrag.chunking import load_corpus
from bankrag.config import get_settings
from bankrag.embeddings import get_embedder
from bankrag.vectorstore import VectorStore


def main() -> None:
    settings = get_settings()
    chunks = load_corpus(settings.docs_dir)
    store = VectorStore(settings, get_embedder(settings))
    store.index(chunks)
    docs = sorted({c.doc_id for c in chunks})
    print(f"Indexed {len(chunks)} chunks from {len(docs)} documents: {', '.join(docs)}")


if __name__ == "__main__":
    main()
