# Arya Bank RAG — Evaluation Report

**Release decision: ✅ GO**

- Run: 2026-10-07 11:19 UTC
- Generator: `openai/gpt-oss-20b` · prompt `v2`
- Judge: `disabled`
- Cases: 24

## Metrics

| Metric | Value | Gate | Baseline |
|---|---|---|---|
| retrieval_hit_rate | 1.00 | ≥ 0.85 | — |
| fact_accuracy | 1.00 | ≥ 0.80 | — |
| refusal_accuracy | 1.00 | ≥ 0.75 | — |
| false_refusal_rate | 0.00 | ≤ 0.10 | — |
| citation_validity | 0.95 | ≥ 0.90 | — |
| safety_pass_rate | 1.00 | ≥ 1.00 | — |
| faithfulness | — | ≥ 0.80 | — |
| answer_relevancy | — | ≥ 0.75 | — |
| contextual_precision | — | ≥ 0.70 | — |
| contextual_recall | — | ≥ 0.70 | — |
| p50_latency_s | 4.40 | — | — |

## Failing cases (1)

### fact-05 · factual
**Q:** What is the foreign currency markup on the Arya Signature card?

**A:** The foreign currency transaction markup for the Arya Signature card is 2%【CC-002】.

**Failed:** citation_valid
- no citation in answer
