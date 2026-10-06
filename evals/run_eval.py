"""Run the full evaluation and produce a release-readiness report.

Usage:
    python -m evals.run_eval                     # deterministic checks + LLM judge
    python -m evals.run_eval --no-judge          # deterministic checks only (fast, cheap)
    python -m evals.run_eval --prompt-version v1_naive   # evaluate another prompt
    python -m evals.run_eval --update-baseline   # save this run as the new baseline

Exit code is 0 when the release decision is GO, 1 when it is NO-GO — so CI can block
a prompt or model change that makes the assistant worse.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

from bankrag.config import PROJECT_ROOT, get_settings
from bankrag.llm import QuotaExhaustedError
from bankrag.rag import RAGAssistant, RAGResponse
from evals.checks import CheckResults, run_checks
from evals.dataset import GoldenCase, load_golden_set

REPORTS_DIR = PROJECT_ROOT / "reports"
BASELINE_PATH = REPORTS_DIR / "baseline.json"
THRESHOLDS_PATH = Path(__file__).parent / "thresholds.json"
JUDGE_METRICS = ["faithfulness", "answer_relevancy", "contextual_precision", "contextual_recall"]


# --------------------------------------------------------------------------- judge
def build_judge_metrics(names: list[str]):
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        FaithfulnessMetric,
    )

    from evals.judge import GroqJudge

    judge = GroqJudge(get_settings())
    factories = {
        "faithfulness": FaithfulnessMetric,
        "answer_relevancy": AnswerRelevancyMetric,
        "contextual_precision": ContextualPrecisionMetric,
        "contextual_recall": ContextualRecallMetric,
    }
    # async_mode=False keeps calls sequential, which suits free-tier rate limits.
    return {n: factories[n](model=judge, async_mode=False, include_reason=True) for n in names}


def judge_case(case: GoldenCase, response: RAGResponse, metrics: dict) -> dict:
    from deepeval.test_case import LLMTestCase

    test_case = LLMTestCase(
        input=case.question,
        actual_output=response.answer,
        expected_output=case.expected_answer,
        retrieval_context=response.contexts,
    )
    results = {}
    for name, metric in metrics.items():
        try:
            metric.measure(test_case)
            results[name] = {"score": round(float(metric.score), 3), "reason": metric.reason}
        except QuotaExhaustedError:
            raise
        except Exception as exc:  # one flaky judge call should not kill the whole run
            results[name] = {"score": None, "reason": f"judge error: {exc}"}
    return results


# ----------------------------------------------------------------------- aggregate
def _rate(values: list[bool | None]) -> float | None:
    applicable = [v for v in values if v is not None]
    return round(sum(applicable) / len(applicable), 3) if applicable else None


def aggregate(records: list[dict]) -> dict:
    checks = [r["checks"] for r in records]
    summary = {
        "retrieval_hit_rate": _rate([c["retrieval_hit"] for c in checks]),
        "fact_accuracy": _rate([c["fact_match"] for c in checks]),
        "refusal_accuracy": _rate([c["refusal_correct"] for c in checks]),
        "false_refusal_rate": _rate([c["false_refusal"] for c in checks]),
        "citation_validity": _rate([c["citation_valid"] for c in checks]),
        "safety_pass_rate": _rate([c["safety_pass"] for c in checks]),
    }
    for name in JUDGE_METRICS:
        scores = [
            r["judge"][name]["score"]
            for r in records
            if r.get("judge") and r["judge"].get(name, {}).get("score") is not None
        ]
        summary[name] = round(statistics.mean(scores), 3) if scores else None
    latencies = [r["latency_s"] for r in records]
    summary["p50_latency_s"] = round(statistics.median(latencies), 3) if latencies else None
    return summary


def decide(summary: dict, baseline: dict | None, thresholds: dict) -> tuple[str, list[str]]:
    reasons = []
    for name, minimum in thresholds["min"].items():
        value = summary.get(name)
        if value is not None and value < minimum:
            reasons.append(f"{name} {value:.2f} is below the {minimum:.2f} gate")
    for name, maximum in thresholds["max"].items():
        value = summary.get(name)
        if value is not None and value > maximum:
            reasons.append(f"{name} {value:.2f} is above the {maximum:.2f} limit")
    if baseline:
        tolerance = thresholds["regression_tolerance"]
        for name, base in baseline["summary"].items():
            value = summary.get(name)
            if value is None or base is None or name.endswith("latency_s"):
                continue
            lower_is_better = name in thresholds["max"]
            drop = (value - base) if lower_is_better else (base - value)
            if drop > tolerance:
                reasons.append(f"{name} regressed from {base:.2f} to {value:.2f} versus baseline")
    return ("GO" if not reasons else "NO-GO"), reasons


# -------------------------------------------------------------------------- report
def _fmt(value) -> str:
    return "—" if value is None else f"{value:.2f}"


def write_markdown(report: dict, path: Path) -> None:
    s, base = report["summary"], (report.get("baseline_summary") or {})
    gates = {**report["thresholds"]["min"], **report["thresholds"]["max"]}
    icon = "✅" if report["decision"] == "GO" else "⛔"
    lines = [
        "# Arya Bank RAG — Evaluation Report",
        "",
        f"**Release decision: {icon} {report['decision']}**",
        "",
        f"- Run: {report['run_at']}",
        f"- Generator: `{report['generator_model']}` · prompt `{report['prompt_version']}`",
        f"- Judge: `{report['judge_model'] or 'disabled'}`",
        f"- Cases: {report['n_cases']}",
        "",
    ]
    if report["reasons"]:
        lines += ["## Why it is blocked", ""] + [f"- {r}" for r in report["reasons"]] + [""]
    lines += [
        "## Metrics",
        "",
        "| Metric | Value | Gate | Baseline |",
        "|---|---|---|---|",
    ]
    for name, value in s.items():
        gate = gates.get(name)
        direction = "≤" if name in report["thresholds"]["max"] else "≥"
        lines.append(
            f"| {name} | {_fmt(value)} | {direction + ' ' + _fmt(gate) if gate is not None else '—'} | {_fmt(base.get(name))} |"
        )
    failed = [r for r in report["cases"] if r["failures"]]
    lines += ["", f"## Failing cases ({len(failed)})", ""]
    if not failed:
        lines.append("None 🎉")
    for r in failed:
        lines += [
            f"### {r['id']} · {r['category']}",
            f"**Q:** {r['question']}",
            "",
            f"**A:** {r['answer']}",
            "",
            f"**Failed:** {', '.join(r['failures'])}",
        ]
        lines += [f"- {n}" for n in r["checks"]["notes"]]
        for name, res in (r.get("judge") or {}).items():
            if res["score"] is not None and res["score"] < gates.get(name, 0):
                lines.append(f"- {name} {res['score']:.2f}: {res['reason']}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-judge", action="store_true", help="skip LLM-as-a-judge metrics")
    parser.add_argument("--metrics", default=",".join(JUDGE_METRICS), help="comma-separated judge metrics")
    parser.add_argument("--limit", type=int, help="only run the first N cases")
    parser.add_argument("--prompt-version", help="override PROMPT_VERSION for this run")
    parser.add_argument("--update-baseline", action="store_true", help="save this run as the baseline")
    parser.add_argument("--output-dir", type=Path, default=REPORTS_DIR)
    args = parser.parse_args(argv)

    if args.prompt_version:
        os.environ["PROMPT_VERSION"] = args.prompt_version
    settings = get_settings()
    use_judge = not args.no_judge and settings.llm_provider != "stub"

    cases = load_golden_set()[: args.limit]
    assistant = RAGAssistant(settings)
    metrics = build_judge_metrics(args.metrics.split(",")) if use_judge else {}
    thresholds = json.loads(THRESHOLDS_PATH.read_text())

    records = []
    incomplete: list[str] = []
    for i, case in enumerate(cases, 1):
        try:
            response = assistant.answer(case.question)
        except QuotaExhaustedError as exc:
            incomplete.append(f"stopped after {i - 1} of {len(cases)} cases: {exc}")
            print(f"[{i:>2}/{len(cases)}] {exc}", flush=True)
            break
        checks: CheckResults = run_checks(case, response)
        record = {
            "id": case.id,
            "category": case.category,
            "question": case.question,
            "answer": response.answer,
            "retrieved": [h.chunk.chunk_id for h in response.retrieved],
            "latency_s": response.latency_s,
            "checks": dataclasses.asdict(checks),
            "failures": checks.failures(),
        }
        # Judge only real answers: refusals are already scored by the refusal checks.
        if metrics and not case.must_refuse and not checks.false_refusal:
            try:
                record["judge"] = judge_case(case, response, metrics)
            except QuotaExhaustedError as exc:
                incomplete.append(f"LLM judge stopped at case {case.id}: {exc}")
                print(f"  judge disabled: {exc}", flush=True)
                metrics = {}
                record["judge"] = {}
            for name, res in record["judge"].items():
                gate = thresholds["min"].get(name)
                if res["score"] is not None and gate is not None and res["score"] < gate:
                    record["failures"].append(f"low_{name}")
        status = "FAIL " + ",".join(record["failures"]) if record["failures"] else "pass"
        print(f"[{i:>2}/{len(cases)}] {case.id:<10} {status}", flush=True)
        records.append(record)

    summary = aggregate(records)
    baseline = json.loads(BASELINE_PATH.read_text()) if BASELINE_PATH.exists() and not args.update_baseline else None
    decision, reasons = decide(summary, baseline, thresholds)
    if incomplete:
        decision, reasons = "NO-GO", [f"evaluation incomplete — {r}" for r in incomplete] + reasons

    report = {
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "generator_model": assistant.llm.model,
        "judge_model": settings.judge_model if use_judge else None,
        "prompt_version": settings.prompt_version,
        "n_cases": len(records),
        "summary": summary,
        "baseline_summary": baseline["summary"] if baseline else None,
        "thresholds": {k: v for k, v in thresholds.items() if not k.startswith("_")},
        "decision": decision,
        "reasons": reasons,
        "cases": records,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "latest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(report, args.output_dir / "latest.md")
    if args.update_baseline:
        BASELINE_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Baseline saved to {BASELINE_PATH.relative_to(PROJECT_ROOT)}")

    print("\n" + "\n".join(f"  {k:<22} {_fmt(v)}" for k, v in summary.items()))
    print(f"\nRelease decision: {decision}")
    for r in reasons:
        print(f"  - {r}")
    if os.getenv("GITHUB_ACTIONS"):
        metrics_line = " · ".join(f"{k}={_fmt(v)}" for k, v in summary.items() if v is not None)
        print(f"::notice title=Release decision: {decision}::{metrics_line}")
        for r in reasons[:9]:
            print(f"::warning title=Gate failed::{r}")
    print(f"Report: {(args.output_dir / 'latest.md').relative_to(PROJECT_ROOT) if args.output_dir.is_relative_to(PROJECT_ROOT) else args.output_dir / 'latest.md'}")
    return 0 if decision == "GO" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # Surface setup errors (bad key, retired model, rate limit) as a clear CI annotation.
        message = f"{type(exc).__name__}: {exc}".replace("\n", " ")[:900]
        if os.getenv("GITHUB_ACTIONS"):
            print(f"::error title=Evaluation crashed::{message}")
        raise
