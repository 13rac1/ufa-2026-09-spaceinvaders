"""Tests for results.json shape, run numbering and record_and_commit."""

from pathlib import Path
import json
import subprocess

import pytest

from invaders.results import (
    append_run,
    build_model_entry,
    check_consistency,
    load_results,
    record_and_commit,
    write_results,
)


def make_record(player="random", score=1.0, decisions=5, steps=5, p50=1.0, p95=2.0):
    return {
        "seed": 1,
        "score": score,
        "steps": steps,
        "frames": steps * 4,
        "lives_lost": 0,
        "terminated": False,
        "truncated": False,
        "model_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "latency_ms_p50": p50,
        "latency_ms_p95": p95,
        "latency_ms_total": p50 * decisions,
        "errors_by_status": {},
        "retries": 0,
        "fallback_actions": 0,
        "wall_clock_s": 0.5,
        "served_model": "random-policy",
        "player": player,
        "mode": "turn",
        "added_delay_ms": 0,
        "decisions": decisions,
        "max_steps": steps,
    }


def test_load_results_returns_skeleton_when_missing(tmp_path):
    results = load_results(tmp_path / "results.json")
    assert results["schema_version"] == 2
    assert results["runs"] == []
    assert results["baseline"] == {"model": None, "runs": []}
    assert "env_id" in results["config"]


def test_append_run_numbers_across_runs_and_baseline():
    results = load_results("/nonexistent/results.json")

    n1 = append_run(results, make_record(player="random"))
    n2 = append_run(results, make_record(player="llm"))
    n3 = append_run(results, make_record(player="random"))

    assert (n1, n2, n3) == (1, 2, 3)
    assert [r["run"] for r in results["runs"]] == [1, 3]
    assert [r["run"] for r in results["baseline"]["runs"]] == [2]


def test_append_run_adds_model_once():
    results = load_results("/nonexistent/results.json")
    model = {
        "role": "decider",
        "provider": "none",
        "requested_model": None,
        "served_model": "random-policy",
        "sdk_package": None,
        "sdk_version": None,
        "player": "random",
    }

    append_run(results, make_record(), model=model)
    append_run(results, make_record(), model=model)

    assert results["models"] == [model]


def test_check_consistency_rejects_bad_records():
    with pytest.raises(ValueError):
        check_consistency(make_record(p50=5.0, p95=1.0))
    with pytest.raises(ValueError):
        check_consistency(make_record(decisions=10, steps=5))
    with pytest.raises(ValueError):
        check_consistency(make_record(score=-1.0))


def test_write_and_load_round_trip(tmp_path):
    results = load_results(tmp_path / "results.json")
    append_run(results, make_record())
    path = tmp_path / "results.json"
    write_results(results, path)

    reloaded = load_results(path)
    assert reloaded == results


def _init_git_repo(path):
    subprocess.run(["git", "init"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    (path / "README.md").write_text("test repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True)


def test_record_and_commit_makes_one_commit(tmp_path):
    _init_git_repo(tmp_path)

    before = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True
    )

    record = make_record()
    model = build_model_entry(
        type("P", (), {"provider": "none", "requested_model": None, "name": "random"})()
    )
    record_and_commit(record, tmp_path, push=False, model=model)

    after = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True
    )
    assert int(after.stdout) - int(before.stdout) == 1

    log = subprocess.run(
        ["git", "log", "-1", "--pretty=%s"], cwd=tmp_path, capture_output=True, text=True, check=True
    )
    assert log.stdout.strip() == "data(results): run 1, random, score 1"

    results_path = tmp_path / "results.json"
    assert results_path.exists()
    with open(results_path) as f:
        saved = json.load(f)
    assert saved["runs"][0]["run"] == 1
    assert saved["models"] == [model]


class _Player:
    def __init__(self, name, provider):
        self.name, self.provider, self.requested_model = name, provider, name


def test_llm_tier_players_are_the_baseline_and_models_list_jev_first():
    from invaders.results import build_model_entry, cost_usd

    results = load_results(Path("/nonexistent/results.json"))
    for name, provider in (("code", "none"), ("llm-t2", "local"), ("jev-t2", "typesafe")):
        record = make_record(player=name)
        append_run(results, record, model=build_model_entry(_Player(name, provider)))
    assert [r["player"] for r in results["baseline"]["runs"]] == ["llm-t2"]
    assert [m["role"] for m in results["models"]] == ["decider", "baseline", "decider"]
    assert results["models"][0]["provider"] == "typesafe"
    assert cost_usd({"input_tokens": 1_000_000, "output_tokens": 5}, "typesafe") == 0.042
    assert cost_usd({"input_tokens": 9, "output_tokens": 9}, "local") == 0.0
