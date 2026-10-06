"""The RAG assistant: retrieve policy chunks, then answer with citations."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from bankrag.chunking import load_corpus
from bankrag.config import Settings, get_settings
from bankrag.embeddings import get_embedder
from bankrag.llm import LLMClient, get_llm
from bankrag.prompts import build_user_message, get_system_prompt
from bankrag.vectorstore import RetrievedChunk, VectorStore

CITATION_PATTERN = re.compile(r"\[([A-Z]+-\d+)\]")


@dataclass
class RAGResponse:
    question: str
    answer: str
    retrieved: list[RetrievedChunk]
    prompt_version: str
    model: str
    latency_s: float

    @property
    def contexts(self) -> list[str]:
        return [r.chunk.as_context() for r in self.retrieved]

    @property
    def retrieved_doc_ids(self) -> list[str]:
        return list(dict.fromkeys(r.chunk.doc_id for r in self.retrieved))

    @property
    def cited_doc_ids(self) -> list[str]:
        return list(dict.fromkeys(CITATION_PATTERN.findall(self.answer)))


class RAGAssistant:
    def __init__(
        self,
        settings: Settings | None = None,
        llm: LLMClient | None = None,
        store: VectorStore | None = None,
    ):
        self.settings = settings or get_settings()
        self.llm = llm or get_llm(self.settings)
        self.store = store or VectorStore(self.settings, get_embedder(self.settings))
        if self.store.count() == 0:
            self.store.index(load_corpus(self.settings.docs_dir))
        self.system_prompt = get_system_prompt(self.settings.prompt_version)

    def answer(self, question: str) -> RAGResponse:
        start = time.perf_counter()
        retrieved = self.store.search(question, self.settings.top_k)
        user_message = build_user_message(question, [r.chunk.as_context() for r in retrieved])
        answer = self.llm.chat(self.system_prompt, user_message).strip()
        return RAGResponse(
            question=question,
            answer=answer,
            retrieved=retrieved,
            prompt_version=self.settings.prompt_version,
            model=self.llm.model,
            latency_s=round(time.perf_counter() - start, 3),
        )
