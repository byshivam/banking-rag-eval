"""LLM-as-a-judge: plug Groq into DeepEval as the grading model."""

from __future__ import annotations

import asyncio

from deepeval.models import DeepEvalBaseLLM

from bankrag.config import Settings
from bankrag.llm import GroqClient

JUDGE_SYSTEM_PROMPT = (
    "You are a strict, impartial evaluator of AI assistant answers. "
    "Follow the requested output format exactly and return valid JSON when asked."
)


class GroqJudge(DeepEvalBaseLLM):
    def __init__(self, settings: Settings, model_name: str | None = None):
        self._settings = settings
        self._model_name = model_name or settings.judge_model
        super().__init__(self._model_name)

    def load_model(self) -> GroqClient:
        return GroqClient(self._settings, self._model_name)

    def generate(self, prompt: str, schema=None):
        text = self.model.chat(
            JUDGE_SYSTEM_PROMPT, prompt, temperature=0.0, json_mode=schema is not None
        )
        if schema is None:
            return text
        try:
            return schema.model_validate_json(text)
        except Exception:
            # DeepEval will fall back to its own lenient JSON parsing.
            return text

    async def a_generate(self, prompt: str, schema=None):
        return await asyncio.to_thread(self.generate, prompt, schema)

    def get_model_name(self) -> str:
        return f"groq/{self._model_name}"
