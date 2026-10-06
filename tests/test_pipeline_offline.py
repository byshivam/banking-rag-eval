"""End-to-end plumbing tests with the offline stub model (no API key needed)."""

from evals.dataset import load_golden_set
from evals.run_eval import aggregate, decide


def test_retrieval_finds_the_right_document_for_answerable_questions(assistant):
    cases = [c for c in load_golden_set() if c.expected_doc_ids]
    hits = sum(
        set(c.expected_doc_ids) <= set(assistant.answer(c.question).retrieved_doc_ids)
        for c in cases
    )
    # Even simple lexical embeddings should find the right policy most of the time.
    assert hits / len(cases) >= 0.8


def test_response_carries_contexts_and_citations(assistant):
    response = assistant.answer("What is the late payment charge on a credit card?")
    assert response.contexts
    assert response.cited_doc_ids == ["CC-002"]
    assert response.prompt_version == "v2"


def _record(**checks):
    base = dict(retrieval_hit=True, fact_match=True, refusal_correct=None,
                false_refusal=False, citation_valid=True, safety_pass=None, notes=[])
    return {"checks": {**base, **checks}, "latency_s": 0.1}


def test_release_gate_blocks_regressions():
    thresholds = {"min": {"fact_accuracy": 0.8}, "max": {}, "regression_tolerance": 0.05}
    good = aggregate([_record() for _ in range(10)])
    decision, _ = decide(good, None, thresholds)
    assert decision == "GO"

    worse = aggregate([_record()] * 9 + [_record(fact_match=False)])  # 0.9 accuracy
    decision, reasons = decide(worse, {"summary": good}, thresholds)
    assert decision == "NO-GO"
    assert any("regressed" in r for r in reasons)
