"""Read, append to, and commit results.json, the organizers' run-record file."""

import fcntl
import json
import subprocess
from pathlib import Path

import ale_py
import gymnasium

from invaders.env import ENV_ID

SCHEMA_VERSION = 2
STATE_ENCODING = "ram+decode"
RESULTS_FILENAME = "results.json"
LOCK_FILENAME = ".results.lock"

# Input-token prices used for cost_usd, with their source. JEV bills input tokens only.
PRICES = {
    "typesafe": {
        "input_per_mtok_usd": 0.042,
        "output_per_mtok_usd": 0.0,
        "source": "https://docs.typesafe.ai/models.md (2026-09-28)",
    },
    "anthropic": {
        "input_per_mtok_usd": 1.0,
        "output_per_mtok_usd": 5.0,
        "source": "claude-haiku-4-5, Anthropic model price table (cached 2026-09-25)",
    },
}


def is_baseline(player: str) -> bool:
    """The LLM players are the organizers' baseline; they go to baseline.runs."""
    return player.startswith("llm")


def cost_usd(record: dict, provider: str | None) -> float | None:
    """Cost of a run from its token counts and PRICES; None when the price is unknown."""
    if provider in ("none", "laya", "local"):
        return 0.0  # code, or a model served on our own hardware
    price = PRICES.get(provider or "")
    if price is None:
        return None
    return round(
        record["input_tokens"] * price["input_per_mtok_usd"] / 1e6
        + record["output_tokens"] * price["output_per_mtok_usd"] / 1e6,
        6,
    )


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
            "prices": PRICES,
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
    role: str | None = None,
) -> dict:
    """Build a models[] entry from a player and the served model of its run."""
    return {
        "role": role or ("baseline" if is_baseline(player.name) else "decider"),
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
        # The organizers read models[] for the JEV decider and the LLM baseline: list
        # those first, then the other deciders.
        results["models"].sort(
            key=lambda m: (m.get("provider") != "typesafe", m.get("role") != "baseline")
        )

    if record.get("max_steps") is not None:
        results["config"]["max_steps"] = record["max_steps"]

    if is_baseline(record.get("player", "")):
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

    if model is not None and "cost_usd" not in record:
        record = {**record, "cost_usd": cost_usd(record, model.get("provider"))}

    # Two bench processes may finish games at the same time: hold the lock from the
    # read of results.json to the push, so no run is lost and git never collides.
    with open(repo_dir / LOCK_FILENAME, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        results = load_results(results_path)
        run_number = append_run(results, record, model=model)
        write_results(results, results_path)

        subprocess.run(["git", "add", RESULTS_FILENAME], cwd=repo_dir, check=True)
        message = (
            f"data(results): run {run_number}, {record['player']}, score {record['score']:g}"
        )
        # Commit only results.json, whatever else is staged.
        subprocess.run(
            ["git", "commit", "-m", message, "--", RESULTS_FILENAME], cwd=repo_dir, check=True
        )
        if push:
            subprocess.run(["git", "push"], cwd=repo_dir, check=True)

    return results
