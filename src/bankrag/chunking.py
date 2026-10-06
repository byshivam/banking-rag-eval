"""Split policy documents into retrievable chunks.

Each markdown document is split on its `## ` section headings, so a chunk is one
self-contained policy section (e.g. "Late payment charges"). Long sections are
split further on paragraph boundaries. Every chunk carries the document title and
section heading so it still makes sense when read on its own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

DOC_ID_PATTERN = re.compile(r"Document ID:\s*([A-Z]+-\d+)")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    section: str
    text: str
    source: str

    def as_context(self) -> str:
        """The text shown to the LLM (and to the evaluator) for this chunk."""
        return f"[{self.doc_id}] {self.title} — {self.section}\n{self.text}"


def _split_long(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    parts, current = [], ""
    for para in text.split("\n\n"):
        if current and len(current) + len(para) + 2 > max_chars:
            parts.append(current.strip())
            current = ""
        current += para + "\n\n"
    if current.strip():
        parts.append(current.strip())
    return parts


def chunk_document(path: Path, max_chars: int = 1500) -> list[Chunk]:
    raw = path.read_text(encoding="utf-8")
    title_match = re.search(r"^# (.+)$", raw, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem
    id_match = DOC_ID_PATTERN.search(raw)
    doc_id = id_match.group(1) if id_match else path.stem.upper()

    sections = re.split(r"^## ", raw, flags=re.MULTILINE)
    chunks: list[Chunk] = []
    for section in sections[1:]:  # sections[0] is the title/preamble
        heading, _, body = section.partition("\n")
        heading = re.sub(r"^\d+\.\s*", "", heading).strip()
        for piece in _split_long(body.strip(), max_chars):
            chunks.append(
                Chunk(
                    chunk_id=f"{doc_id}#{len(chunks) + 1}",
                    doc_id=doc_id,
                    title=title,
                    section=heading,
                    text=piece,
                    source=path.name,
                )
            )
    return chunks


def load_corpus(docs_dir: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(docs_dir.glob("*.md")):
        chunks.extend(chunk_document(path))
    if not chunks:
        raise FileNotFoundError(f"No markdown documents found in {docs_dir}")
    return chunks
