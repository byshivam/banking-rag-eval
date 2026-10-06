"""Quality gate against the real model. Runs only when GROQ_API_KEY is set.

    GROQ_API_KEY=... LLM_PROVIDER=groq EMBEDDING_BACKEND=sentence-transformers pytest -m llm
"""

import os

import pytest

pytestmark = pytest.mark.llm

needs_key = pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY") or os.getenv("LLM_PROVIDER") == "stub",
    reason="needs GROQ_API_KEY and LLM_PROVIDER=groq",
)


@needs_key
def test_release_gate_passes_with_real_model(tmp_path):
    from evals.run_eval import main

    assert main(["--output-dir", str(tmp_path)]) == 0, (tmp_path / "latest.md").read_text()
