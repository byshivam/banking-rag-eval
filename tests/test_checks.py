from bankrag.chunking import Chunk
from bankrag.prompts import REFUSAL_MESSAGE
from bankrag.rag import RAGResponse
from bankrag.vectorstore import RetrievedChunk
from evals.checks import contains_all, is_refusal, normalize, run_checks
from evals.dataset import GoldenCase, load_golden_set


def _response(answer: str, doc_ids=("CC-002",)) -> RAGResponse:
    retrieved = [
        RetrievedChunk(Chunk(f"{d}#1", d, "t", "s", "text", "f.md"), score=0.9) for d in doc_ids
    ]
    return RAGResponse("q", answer, retrieved, "v2", "test", 0.1)


def _case(**overrides) -> GoldenCase:
    base = dict(
        id="t-1",
        category="reasoning",
        question="q",
        expected_answer="₹950",
        expected_doc_ids=["CC-002"],
        must_include=["950"],
        must_refuse=False,
    )
    return GoldenCase(**{**base, **overrides})


def test_normalize_handles_indian_number_format():
    assert "300000" in normalize("waived above ₹3,00,000")
    assert "2%" in normalize("a markup of 2 %")


def test_contains_all_supports_alternatives():
    assert contains_all("Interest is paid every quarter.", ["quarterly|every quarter"])
    assert not contains_all("Interest is paid monthly.", ["quarterly|every quarter"])


def test_refusal_detection():
    assert is_refusal(REFUSAL_MESSAGE)
    assert not is_refusal("The late fee is ₹950 [CC-002].")


def test_correct_answer_passes_every_check():
    result = run_checks(_case(), _response("The late payment charge is ₹950 [CC-002]."))
    assert result.failures() == []


def test_wrong_number_fails_fact_check():
    result = run_checks(_case(), _response("The late payment charge is ₹500 [CC-002]."))
    assert "fact_match" in result.failures()


def test_fabricated_citation_is_caught():
    result = run_checks(_case(), _response("The charge is ₹950 [HL-003]."))
    assert "citation_valid" in result.failures()


def test_missing_citation_is_caught():
    result = run_checks(_case(), _response("The charge is ₹950."))
    assert "citation_valid" in result.failures()


def test_answering_out_of_scope_question_fails():
    case = _case(category="out_of_scope", expected_doc_ids=[], must_include=[], must_refuse=True)
    result = run_checks(case, _response("Fixed deposits earn 7% [CC-002]."))
    assert "refusal_correct" in result.failures()


def test_refusing_answerable_question_is_a_false_refusal():
    result = run_checks(_case(), _response(REFUSAL_MESSAGE))
    assert "false_refusal" in result.failures()


def test_unsafe_phrase_fails_safety():
    case = _case(category="safety", must_include=[], must_not_include=["i recommend"])
    result = run_checks(case, _response("I recommend mutual funds [CC-002]."))
    assert "safety_pass" in result.failures()


def test_golden_set_is_valid():
    cases = load_golden_set()
    assert len(cases) >= 20
    assert {c.category for c in cases} == {"factual", "reasoning", "out_of_scope", "safety"}
    for case in cases:
        if case.must_refuse:
            assert not case.expected_doc_ids
