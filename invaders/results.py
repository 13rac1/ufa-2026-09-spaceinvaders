"""Read, append to, and commit results.json, the organizers' run-record file."""

import json
import subprocess
from pathlib import Path

import ale_py
import gymnasium

from invaders.env import ENV_ID

SCHEMA_VERSION = 2
STATE_ENCODING = "ram+decode"
RESULTS_FILENAME = "results.json"


def _default_results() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "models": [],
        "config": {
            "env_id": ENV_ID,
            "frameskip": 4,
            "repeat_action_probability": 0.25,
            "full_action_space": False,
            "max_num_frames_per_episode": 108000,
            "obs_type": "ram",
            "wrappers": [],
            "decision_interval_steps": 1,
            "state_encoding": STATE_ENCODING,
            "ale_py_version": ale_py.__version__,
            "gymnasium_version": gymnasium.__version__,
        },
        "runs": [],
        "baseline": {"model": None, "runs": []},
    }


def load_results(path: Path) -> dict:
    """Read results.json at path, or return a fresh skeleton if it is missing."""
    path = Path(path)
    if not path.exists():
        return _default_results()
    with open(path) as f:
        return json.load(f)


def write_results(results: dict, path: Path) -> None:
    """Write results to path as JSON, with a trailing newline."""
    path = Path(path)
    with open(path, "w") as f:
        json.dump(results, f, indent=2)
        f.write("\n")


def build_model_entry(
    player,
    served_model: str | None = None,
    sdk_package: str | None = None,
    sdk_version: str | None = None,
    role: str = "decider",
) -> dict:
    """Build a models[] entry from a player and the served model of its run."""
    return {
        "role": role,
        "provider": player.provider,
        "requested_model": player.requested_model,
        "served_model": served_model,
        "sdk_package": sdk_package,
        "sdk_version": sdk_version,
        "player": player.name,
    }


def check_consistency(record: dict) -> None:
    if record["latency_ms_p95"] < record["latency_ms_p50"]:
        raise ValueError("latency_ms_p95 must be >= latency_ms_p50")
    if record["model_calls"] > record["decisions"]:
        raise ValueError("model_calls must be <= decisions")
    if record["steps"] < record["decisions"]:
        raise ValueError("steps must be >= decisions")
    if record["score"] < 0:
        raise ValueError("score must be >= 0")


def append_run(results: dict, record: dict, model: dict | None = None) -> int:
    """Add one run record to results, in place. Return its run number.

    A record whose player is "llm" goes to baseline.runs; every other player
    goes to runs. Runs are numbered from 1 across the whole file, in the
    order they are added.
    """
    check_consistency(record)

    run_number = len(results["runs"]) + len(results["baseline"]["runs"]) + 1
    entry = dict(record)
    entry["run"] = run_number

    if model is not None and not any(
        m.get("player") == model.get("player")
        and m.get("requested_model") == model.get("requested_model")
        for m in results["models"]
    ):
        results["models"].append(model)

    if record.get("max_steps") is not None:
        results["config"]["max_steps"] = record["max_steps"]

    if record.get("player") == "llm":
        if model is not None:
            results["baseline"]["model"] = model.get("requested_model") or model.get(
                "served_model"
            )
        results["baseline"]["runs"].append(entry)
    else:
        results["runs"].append(entry)

    return run_number


def record_and_commit(
    record: dict,
    repo_dir: Path,
    push: bool = True,
    model: dict | None = None,
) -> dict:
    """Append record to repo_dir/results.json, write it, then commit and push.

    Runs after every game, including a short or failed one, as the
    organizers require a commit (and push) after every game. model, when
    given, is the models[] entry to add if not already present (see
    build_model_entry).
    """
    repo_dir = Path(repo_dir)
    results_path = repo_dir / RESULTS_FILENAME

    results = load_results(results_path)
    run_number = append_run(results, record, model=model)
    write_results(results, results_path)

    subprocess.run(["git", "add", RESULTS_FILENAME], cwd=repo_dir, check=True)
    message = f"data(results): run {run_number}, {record['player']}, score {record['score']:g}"
    # Commit only results.json, whatever else is staged.
    subprocess.run(
        ["git", "commit", "-m", message, "--", RESULTS_FILENAME], cwd=repo_dir, check=True
    )
    if push:
        subprocess.run(["git", "push"], cwd=repo_dir, check=True)

    return results
