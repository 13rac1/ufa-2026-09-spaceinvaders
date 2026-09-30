"""Diagnose a player on tuning seeds: why games end and where the time goes.

Plays turn-based games outside the results file, several at once, and reports per
game: score, waves reached, end cause, real shots and hits, shots stopped by shields,
and frames per kill.
"""

from multiprocessing import Pool

import numpy as np

from invaders.env import make_env
from invaders.shots import ShotCounter
from invaders.state import decode

INVASION_Y = 160  # a life loss with the lowest alien this low is an invasion


def diagnose_game(args: tuple) -> dict:
    """Play one turn-based game and return its diagnostics."""
    player_factory, seed = args
    player = player_factory()
    env = make_env()
    obs, info = env.reset(seed=seed)
    player.reset(seed)
    previous, previous_frame, previous_action = None, 0, 0
    score, steps, waves = 0.0, 0, 1
    shots = ShotCounter()
    last_left = int(obs[17])
    end_cause = None
    lives = info["lives"]
    done = False
    while not done:
        frame = info.get("episode_frame_number", 0)
        state = decode(obs, env.unwrapped.ale.getScreenRGB(), previous, frame - previous_frame)
        previous, previous_frame = state, frame
        action = player.decide(state, previous_action).action
        ram_before = obs
        obs, reward, terminated, truncated, info = env.step(action)
        shots.step(ram_before, obs, reward)
        score += reward
        steps += 1
        done = terminated or truncated
        if int(obs[17]) > last_left:
            waves += 1
        last_left = int(obs[17])
        if info["lives"] < lives:
            lowest = max((a["y"] for a in state["aliens"]), default=0)
            end_cause = "invasion" if lowest >= INVASION_Y else "bullet"
            lives = info["lives"]
        previous_action = action
    env.close()
    return {
        "seed": seed,
        "score": score,
        "steps": steps,
        "waves": waves,
        "end_cause": end_cause,
        **shots.record(),
        "frames_per_kill": steps * 4 / shots.hits if shots.hits else None,
    }


def diagnose(player_factory, seeds: list[int], processes: int = 4) -> list[dict]:
    with Pool(processes) as pool:
        return pool.map(diagnose_game, [(player_factory, s) for s in seeds])


def summary(rows: list[dict]) -> str:
    scores = [r["score"] for r in rows]
    shots = sum(r["shots"] for r in rows)
    hits = sum(r["shot_hits"] for r in rows)
    blocked = sum(r["shots_into_shields"] for r in rows)
    invasions = sum(r["end_cause"] == "invasion" for r in rows)
    wave2 = sum(r["waves"] >= 2 for r in rows)
    return (
        f"games {len(rows)}  mean {np.mean(scores):.0f}  median {np.median(scores):.0f}  "
        f"stdev {np.std(scores):.0f}\n"
        f"reached wave 2: {wave2}/{len(rows)}  invasion endings: {invasions}/{len(rows)}\n"
        f"shots {shots}  hit rate {hits / max(shots, 1):.2f}  "
        f"shots into shields {blocked}  frames per kill "
        f"{np.mean([r['frames_per_kill'] for r in rows if r['frames_per_kill']]):.0f}"
    )
