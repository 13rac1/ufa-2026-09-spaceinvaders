"""Tests for report.py: the README tables and the latency chart."""

import json
import statistics

from invaders.report import HUMAN_HIGH, HUMAN_LOW, generate_report


def make_record(
    player,
    mode,
    seed,
    score,
    added_delay_ms=0.0,
    decisions=10,
    steps=10,
    p50=5.0,
    p95=10.0,
    model_calls=1,
    input_tokens=100,
    output_tokens=50,
    fallback_actions=0,
    errors_by_status=None,
    served_model="test-model",
    cost_usd=None,
    max_steps=None,
):
    record = {
        "seed": seed,
        "score": score,
        "steps": steps,
        "frames": steps * 4,
        "lives_lost": 0,
        "terminated": True,
        "truncated": False,
        "model_calls": model_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms_p50": p50,
        "latency_ms_p95": p95,
        "latency_ms_total": p50 * decisions,
        "errors_by_status": errors_by_status or {},
        "retries": 0,
        "fallback_actions": fallback_actions,
        "wall_clock_s": 1.0,
        "served_model": served_model,
        "player": player,
        "mode": mode,
        "added_delay_ms": added_delay_ms,
        "decisions": decisions,
        "max_steps": max_steps,
    }
    if cost_usd is not None:
        record["cost_usd"] = cost_usd
    return record


def make_results(runs, baseline_runs=None):
    return {
        "schema_version": 2,
        "models": [],
        "config": {},
        "runs": runs,
        "baseline": {"model": None, "runs": baseline_runs or []},
    }


def test_report_summary_table_has_expected_numbers(tmp_path):
    runs = [
        make_record("code", "turn", 101, 100.0),
        make_record("code", "turn", 102, 200.0),
        make_record("random", "turn", 101, 20.0),
    ]
    results = make_results(runs)
    results_path = tmp_path / "results.json"
    results_path.write_text(json.dumps(results))

    out_dir = tmp_path / "report"
    generate_report(results_path, out_dir)

    readme = (out_dir / "README.md").read_text()
    assert (out_dir / "latency_curve.png").exists()
    assert (out_dir / "latency_curve.png").stat().st_size > 0

    assert "This file is generated" in readme

    code_scores = [100.0, 200.0]
    mean = statistics.mean(code_scores)
    median = statistics.median(code_scores)
    stdev = statistics.stdev(code_scores)
    human_norm = statistics.mean(
        [(s - HUMAN_LOW) / (HUMAN_HIGH - HUMAN_LOW) for s in code_scores]
    )

    assert f"| code | turn | 2 | {mean:.1f} | {median:.1f} | 100.0 | 200.0 | {stdev:.1f} | " in readme
    assert f"{human_norm:.3f}" in readme
    assert "| random | turn | 1 | 20.0 | 20.0 | 20.0 | 20.0 | 0.0 |" in readme


def test_report_is_deterministic(tmp_path):
    runs = [
        make_record("code", "turn", 101, 100.0),
        make_record("random", "turn", 101, 20.0),
    ]
    results_path = tmp_path / "results.json"
    results_path.write_text(json.dumps(make_results(runs)))

    generate_report(results_path, tmp_path / "report1")
    generate_report(results_path, tmp_path / "report2")

    text1 = (tmp_path / "report1" / "README.md").read_text()
    text2 = (tmp_path / "report2" / "README.md").read_text()
    assert text1 == text2


def test_head_to_head_counts_wins(tmp_path):
    runs = [
        make_record("jev", "turn", 101, 300.0),
        make_record("jev", "turn", 102, 100.0),
        make_record("jev", "turn", 103, 50.0),
    ]
    baseline_runs = [
        make_record("llm", "turn", 101, 200.0),
        make_record("llm", "turn", 102, 100.0),
        make_record("llm", "turn", 104, 999.0),  # seed not shared with jev
    ]
    results_path = tmp_path / "results.json"
    results_path.write_text(json.dumps(make_results(runs, baseline_runs)))

    generate_report(results_path, tmp_path / "report")
    readme = (tmp_path / "report" / "README.md").read_text()

    # seed 101: jev 300 > llm 200 -> jev win
    # seed 102: jev 100 == llm 100 -> tie
    # seed 103 and 104 are not shared, excluded
    assert "| 101 | 300.0 | 200.0 | jev |" in readme
    assert "| 102 | 100.0 | 100.0 | tie |" in readme
    assert "103" not in readme.split("Head-to-head")[1].split("##")[0]
    assert "Total: jev wins 1, llm wins 0, ties 1 (of 2 shared seeds)." in readme


def test_head_to_head_omitted_cleanly_when_llm_absent(tmp_path):
    runs = [make_record("jev", "turn", 101, 300.0)]
    results_path = tmp_path / "results.json"
    results_path.write_text(json.dumps(make_results(runs)))

    generate_report(results_path, tmp_path / "report")
    readme = (tmp_path / "report" / "README.md").read_text()

    section = readme.split("Head-to-head")[1].split("##")[0]
    assert "No head-to-head: llm has no turn-mode runs." in section
    assert "| seed |" not in section
