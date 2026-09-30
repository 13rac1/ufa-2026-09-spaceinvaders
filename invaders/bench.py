"""Build and run the evaluation matrix: one game per combination, recorded as `run` does."""

from dataclasses import dataclass
from pathlib import Path

from invaders.harness import run_game
from invaders.results import build_model_entry, cost_usd, record_and_commit


@dataclass(frozen=True)
class Game:
    """One (player, mode, seed, added_delay_ms) combination to play."""

    player: str
    mode: str
    seed: int
    added_delay_ms: float


# Players whose realtime runs sweep the added delays to draw the latency curve.
LATENCY_CURVE_PLAYERS = ("code", "code-la")


def build_matrix(
    players: list[str], seeds: list[int], modes: list[str], delays: list[float]
) -> list[Game]:
    """Build the evaluation matrix in a fixed, deterministic order.

    delays applies only to the code players (LATENCY_CURVE_PLAYERS) in mode
    "realtime"; every other
    (player, mode) combination runs once per seed at added_delay_ms 0.
    """
    games = []
    for player in players:
        for mode in modes:
            if mode == "realtime" and player in LATENCY_CURVE_PLAYERS:
                for delay in delays:
                    for seed in seeds:
                        games.append(Game(player, mode, seed, float(delay)))
            else:
                for seed in seeds:
                    games.append(Game(player, mode, seed, 0.0))
    return games


def existing_keys(results: dict) -> set[tuple]:
    """Return the (player, version, mode, seed, added_delay_ms, max_steps) keys recorded."""
    records = results["runs"] + results["baseline"]["runs"]
    return {
        (
            r["player"], r.get("player_version"), r["mode"], r["seed"],
            float(r["added_delay_ms"]), r.get("max_steps"),
        )
        for r in records
    }


def game_key(game: Game, max_steps: int | None, version: str | None = None) -> tuple:
    """The key existing_keys uses for a game, so bench can check --skip-existing.

    A new player version is a new key: its games are played, not skipped.
    """
    return (game.player, version, game.mode, game.seed, game.added_delay_ms, max_steps)


def play_and_record(
    player,
    seed: int,
    mode: str,
    added_delay_ms: float,
    max_steps: int | None,
    repo_dir: Path,
    no_commit: bool,
    no_push: bool,
    sdk_package: str | None,
    sdk_version: str | None,
    record_video: str | None = None,
    log_path: str | None = None,
    notes: str | None = None,
) -> dict:
    """Play one game and, unless no_commit, record and commit it.

    Shared by the `run` and `bench` commands so a game is always played and
    recorded the same way.
    """
    record = run_game(
        player,
        seed=seed,
        mode=mode,
        added_delay_ms=added_delay_ms,
        max_steps=max_steps,
        record_video=record_video,
        log_path=log_path,
    )
    tier = getattr(player, "input_tier", None)
    record["input_tier"] = f"{tier}s" if getattr(player, "strategy", False) else tier
    record["question_version"] = getattr(player, "question_version", None)
    if notes:
        record["notes"] = notes  # the organizers' per-run note: what changed and why

    print(
        f"player={record['player']} seed={record['seed']} mode={record['mode']} "
        f"score={record['score']} steps={record['steps']} decisions={record['decisions']} "
        f"latency_p50={record['latency_ms_p50']:.2f}ms latency_p95={record['latency_ms_p95']:.2f}ms"
    )

    model = build_model_entry(
        player,
        served_model=record["served_model"],
        sdk_package=sdk_package,
        sdk_version=sdk_version,
    )
    record["cost_usd"] = cost_usd(record, model.get("provider"))
    if not no_commit:
        model = build_model_entry(
            player,
            served_model=record["served_model"],
            sdk_package=sdk_package,
            sdk_version=sdk_version,
        )
        record_and_commit(record, repo_dir, push=not no_push, model=model)

    return record
