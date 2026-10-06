"""Runtime settings, read from environment variables (and a local .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def _env(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    return value or default


@dataclass(frozen=True)
class Settings:
    groq_api_key: str = field(default_factory=lambda: _env("GROQ_API_KEY", ""))
    groq_base_url: str = field(
        default_factory=lambda: _env("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    )
    generator_model: str = field(
        default_factory=lambda: _env("GENERATOR_MODEL", "openai/gpt-oss-20b")
    )
    judge_model: str = field(
        default_factory=lambda: _env("JUDGE_MODEL", "openai/gpt-oss-120b")
    )
    prompt_version: str = field(default_factory=lambda: _env("PROMPT_VERSION", "v2"))
    # "groq" uses the real API; "stub" is a deterministic offline fake for unit tests.
    llm_provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "groq"))
    embedding_backend: str = field(
        default_factory=lambda: _env("EMBEDDING_BACKEND", "sentence-transformers")
    )
    embedding_model: str = field(
        default_factory=lambda: _env(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
    )
    top_k: int = field(default_factory=lambda: int(_env("TOP_K", "4")))
    docs_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "docs")
    chroma_dir: Path = field(
        default_factory=lambda: Path(_env("CHROMA_DIR", str(PROJECT_ROOT / ".chroma")))
    )


def get_settings() -> Settings:
    return Settings()
