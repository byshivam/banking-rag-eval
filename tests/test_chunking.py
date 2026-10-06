from bankrag.chunking import load_corpus
from bankrag.config import get_settings


def test_every_document_is_chunked_with_its_id():
    chunks = load_corpus(get_settings().docs_dir)
    doc_ids = {c.doc_id for c in chunks}
    assert doc_ids == {"SAV-001", "CC-002", "HL-003", "KYC-004", "DIS-005"}


def test_chunk_ids_are_unique_and_context_is_self_describing():
    chunks = load_corpus(get_settings().docs_dir)
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    for chunk in chunks:
        context = chunk.as_context()
        assert context.startswith(f"[{chunk.doc_id}]")
        assert chunk.section in context
        assert chunk.text.strip()


def test_sections_are_split_on_headings():
    chunks = load_corpus(get_settings().docs_dir)
    sections = {c.section for c in chunks if c.doc_id == "CC-002"}
    assert "Late payment charges" in sections
    assert "Rewards" in sections
