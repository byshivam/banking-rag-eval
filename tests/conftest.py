import os
import tempfile

import pytest

# Unit tests run fully offline: fake LLM, lexical embeddings, throwaway vector store.
os.environ.setdefault("LLM_PROVIDER", "stub")
os.environ.setdefault("EMBEDDING_BACKEND", "hash")
os.environ.setdefault("CHROMA_DIR", tempfile.mkdtemp(prefix="bankrag-test-"))


@pytest.fixture(scope="session")
def assistant():
    from bankrag.config import get_settings
    from bankrag.embeddings import HashingEmbedder
    from bankrag.llm import StubClient
    from bankrag.rag import RAGAssistant
    from bankrag.vectorstore import VectorStore

    settings = get_settings()
    store = VectorStore(settings, HashingEmbedder(), persistent=False)
    return RAGAssistant(settings, llm=StubClient(), store=store)
