"""Replay recorded games of the deterministic players and check the scores match.

A game is fixed by its seed: the environment's sticky actions and the random player's
choices both come from it. Replaying a recorded code or random game in turn mode must
give the recorded score exactly. Only runs of the current player version can replay.
"""

from invaders.harness import run_game

REPLAYABLE = ("code", "code-la", "random", "always-fire")


def verify(results: dict, players: dict, limit: int | None = None) -> list[dict]:
    """Replay each replayable recorded run and return one row per run checked."""
    rows = []
    for record in results["runs"]:
        if record["player"] not in REPLAYABLE or record["mode"] != "turn":
            continue
        player = players[record["player"]]()
        if record.get("player_version") != getattr(player, "version", None):
            continue  # recorded by an earlier version of the player's code
        replay = run_game(player, record["seed"], "turn", max_steps=record.get("max_steps"))
        rows.append(
            {
                "run": record["run"],
                "player": record["player"],
                "seed": record["seed"],
                "recorded": record["score"],
                "replayed": replay["score"],
                "match": replay["score"] == record["score"],
            }
        )
        if limit is not None and len(rows) >= limit:
            break
    return rows
