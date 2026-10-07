"""LLM clients.

`GroqClient` talks to Groq's free OpenAI-compatible API. `StubClient` is a
deterministic fake used by offline unit tests, so CI can check the plumbing without
an API key.
"""

from __future__ import annotations

import re
import time
from typing import Protocol

from bankrag.config import Settings
from bankrag.prompts import REFUSAL_MESSAGE


class LLMClient(Protocol):
    model: str

    def chat(
        self, system: str, user: str, temperature: float = 0.0, json_mode: bool = False
    ) -> str: ...


class QuotaExhaustedError(RuntimeError):
    """The provider's daily quota is used up — retrying now will not help."""


def _is_daily_limit(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in ("per day", "tokens per day", "requests per day", "(tpd)", "(rpd)"))


class GroqClient:
    def __init__(self, settings: Settings, model: str, max_retries: int = 6, reasoning_effort: str | None = None):
        if not settings.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Copy .env.example to .env and add your free key "
                "from https://console.groq.com"
            )
        from openai import OpenAI

        self.model = model
        self.max_retries = max_retries
        self.reasoning_effort = reasoning_effort
        self._client = OpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)

    def chat(
        self, system: str, user: str, temperature: float = 0.0, json_mode: bool = False
    ) -> str:
        from openai import APIConnectionError, InternalServerError, RateLimitError

        kwargs: dict = {"response_format": {"type": "json_object"}} if json_mode else {}
        if self.reasoning_effort:
            # Reasoning tokens count against the daily quota.
            kwargs["extra_body"] = {"reasoning_effort": self.reasoning_effort}
        for attempt in range(self.max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    temperature=temperature,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    **kwargs,
                )
                return response.choices[0].message.content or ""
            except RateLimitError as exc:
                if _is_daily_limit(exc):
                    raise QuotaExhaustedError(
                        f"Groq daily limit reached for {self.model}. It resets within 24 hours; "
                        "meanwhile use --limit or fewer --metrics."
                    ) from exc
                if attempt == self.max_retries - 1:
                    raise
                # Per-minute limits clear quickly; back off and try again.
                time.sleep(min(30, 2 ** (attempt + 1)))
            except (APIConnectionError, InternalServerError):
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(min(30, 2 ** (attempt + 1)))
        raise RuntimeError("unreachable")


class StubClient:
    """Answers by quoting the first retrieved context — or refuses if there is none."""

    model = "stub"

    def chat(
        self, system: str, user: str, temperature: float = 0.0, json_mode: bool = False
    ) -> str:
        match = re.search(r"CONTEXT:\n\[([A-Z]+-\d+)\][^\n]*\n(.+?)(?:\n\n---|\n\nCUSTOMER)", user, re.S)
        if not match:
            return REFUSAL_MESSAGE
        doc_id, text = match.group(1), match.group(2)
        first_sentence = re.split(r"(?<=[.!?])\s", text.strip())[0]
        return f"{first_sentence} [{doc_id}]"


def get_llm(settings: Settings, model: str | None = None) -> LLMClient:
    if settings.llm_provider == "stub":
        return StubClient()
    if settings.llm_provider == "groq":
        return GroqClient(settings, model or settings.generator_model)
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r}")
