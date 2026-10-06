from evals.update_readme import END, START, is_complete, render, update


def _report(decision="GO", reasons=(), fact=1.0):
    return {
        "run_at": "2026-10-07 02:30 UTC", "generator_model": "gen", "judge_model": "judge",
        "prompt_version": "v2", "n_cases": 2, "decision": decision, "reasons": list(reasons),
        "summary": {"fact_accuracy": fact, "false_refusal_rate": 0.0, "faithfulness": None,
                    "p50_latency_s": 1.2},
        "thresholds": {"min": {"fact_accuracy": 0.8}, "max": {"false_refusal_rate": 0.1}},
        "cases": [
            {"id": "a", "category": "factual", "failures": [], "checks": {"notes": []}},
            {"id": "b", "category": "factual", "failures": ["fact_match"],
             "checks": {"notes": ["missing expected facts: ['950']"]}},
        ],
    }


def test_render_shows_scores_findings_and_trend():
    block = render(_report(fact=0.9), previous=_report(fact=1.0))
    assert block.startswith(START) and block.endswith(END)
    assert "**90%**" in block and "🔴 -10 pts" in block
    assert "`b` (factual): missing expected facts" in block
    assert "Faithfulness" not in block  # metrics without a score are hidden


def test_update_replaces_only_the_marked_block(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(f"intro\n{START}\nold\n{END}\noutro\n", encoding="utf-8")
    assert update(readme, _report())
    text = readme.read_text(encoding="utf-8")
    assert text.startswith("intro\n") and text.endswith("outro\n") and "old" not in text


def test_incomplete_runs_are_skipped():
    assert not is_complete(_report(reasons=["evaluation incomplete — judge quota"]))
    assert is_complete(_report(reasons=["fact_accuracy below gate"]))
