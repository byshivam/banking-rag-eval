"""Load the golden evaluation set."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.jsonl"
CATEGORIES = {"factual", "reasoning", "out_of_scope", "safety"}


@dataclass(frozen=True)
class GoldenCase:
    id: str
    category: str
    question: str
    expected_answer: str
    expected_doc_ids: list[str]
    must_include: list[str]
    must_refuse: bool
    must_not_include: list[str] = field(default_factory=list)


def load_golden_set(path: Path = GOLDEN_SET_PATH) -> list[GoldenCase]:
    cases = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        case = GoldenCase(**json.loads(line))
        if case.category not in CATEGORIES:
            raise ValueError(f"{path.name}:{line_no} unknown category {case.category!r}")
        cases.append(case)
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate case IDs in golden set")
    return cases
