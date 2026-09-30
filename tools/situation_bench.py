"""Score model players on fixed game situations, without playing games.

States come from code-player games on tuning seeds. Each state is sent once to each
player, through the player's own request (its tier and question). The code player's
verdicts score the answers; they are never sent to a model.

Usage: python tools/situation_bench.py collect STATES.json
       python tools/situation_bench.py score STATES.json jev-t1,jev-t1s [THREADS] [ORDER]

ORDER (System One players only) lists the six actions in the order the question offers
them, for example LEFTFIRE,RIGHTFIRE,LEFT,RIGHT,FIRE,NOOP; "random" shuffles them for every
request. The default is the recorded order.
"""

import json
import os
import random
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from invaders.env import make_env  # noqa: E402
from invaders.players.code_player import choose  # noqa: E402
from invaders.state import ACTIONS, SHIP_MIN_X, decode  # noqa: E402

PER_KIND = 75


def kind(state: dict) -> str | None:
    f = state["features"]
    if state["ship_x"] == SHIP_MIN_X and f["safe_stay"]:
        return "wall"
    if not f["safe_stay"] and (f["safe_left"] or f["safe_right"]):
        return "danger"
    if f["safe_stay"] and f["aligned"] and f["can_fire"] and not f["under_shield"]:
        return "fire"
    if f["safe_stay"] and not f["aligned"] and f["target_dx"]:
        side_safe = f["safe_right"] if f["target_dx"] > 0 else f["safe_left"]
        if side_safe:
            return "approach"
    return None


def collect(path: str) -> None:
    pools: dict[str, list] = {"wall": [], "danger": [], "fire": [], "approach": []}
    for seed in range(1, 21):
        env = make_env()
        obs, info = env.reset(seed=seed)
        previous, previous_frame, done = None, 0, False
        while not done:
            frame = info["episode_frame_number"]
            state = decode(obs, env.unwrapped.ale.getScreenRGB(), previous, frame - previous_frame)
            previous, previous_frame = state, frame
            k = kind(state)
            if k:
                pools[k].append(state)
            obs, _r, terminated, truncated, info = env.step(choose(state["features"]))
            done = terminated or truncated
    rng = random.Random(0)
    chosen = {k: rng.sample(v, min(PER_KIND, len(v))) for k, v in pools.items()}
    json.dump(chosen, open(path, "w"))
    print({k: len(v) for k, v in chosen.items()})


def correct(k: str, state: dict, action: str) -> bool:
    f = state["features"]
    move = 1 if action.startswith("RIGHT") else -1 if action.startswith("LEFT") else 0
    if k == "wall":
        return move != -1
    if k == "danger":
        return (move == -1 and f["safe_left"]) or (move == 1 and f["safe_right"])
    if k == "fire":
        return "FIRE" in action
    return move == (1 if f["target_dx"] > 0 else -1)  # approach


def reordered_decision(player, state: dict, order: list[str] | None):
    """Ask a System One player its question with the options in the given order."""
    from invaders.players.base import Decision
    from invaders.question import build_questions, build_request_state

    names = random.sample(ACTIONS, len(ACTIONS)) if order == ["random"] else order
    question = build_questions(player.input_tier, player.strategy)["action"]
    question = {**question, "criteria": {a: question["criteria"][a] for a in names}}
    data, calls, retries, status = player._ask(build_request_state(state, player.input_tier),
                                               {"action": question})
    answer = (data or {}).get("answers", {}).get("action") or {}
    usage = (data or {}).get("usage", {})
    choice = answer.get("choice")
    return Decision(action=ACTIONS.index(choice) if choice in ACTIONS else 0,
                    model_calls=calls, input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0), error_status=status,
                    retries=retries, fallback=choice not in ACTIONS)


def score(path: str, names: list[str], threads: int, order: list[str] | None = None) -> None:
    from invaders.__main__ import PLAYERS
    from invaders.results import PRICES

    states = json.load(open(path))
    with ThreadPoolExecutor(threads) as pool:
        for name in names:
            player = PLAYERS[name]()
            price = PRICES.get(player.provider)
            tokens, line = [0, 0], []
            for k, group in states.items():
                if order:
                    decisions = list(pool.map(lambda st: reordered_decision(player, st, order), group))
                else:
                    decisions = list(pool.map(lambda st: player.decide(st, 0), group))
                moves = [ACTIONS[d.action] for d in decisions if not d.fallback]
                line_moves = {m: sum(a.startswith(m) for a in moves) for m in ("LEFT", "RIGHT")}
                tokens[0] += sum(d.input_tokens for d in decisions)
                tokens[1] += sum(d.output_tokens for d in decisions)
                answered = [(st, ACTIONS[d.action]) for st, d in zip(group, decisions) if not d.fallback]
                rate = sum(correct(k, st, a) for st, a in answered) / max(len(answered), 1)
                line.append(f"{k} {rate:.2f} (n {len(answered)}, L {line_moves['LEFT']} R {line_moves['RIGHT']})")
            cost = (tokens[0] * price["input_per_mtok_usd"]
                    + tokens[1] * price["output_per_mtok_usd"]) / 1e6 if price else 0.0
            print(f"{name}: " + ", ".join(line) + f"; ${cost:.3f}", flush=True)


if __name__ == "__main__":
    command, path = sys.argv[1], sys.argv[2]
    if command == "collect":
        collect(path)
    else:
        score(path, sys.argv[3].split(","), int(sys.argv[4]) if len(sys.argv) > 4 else 6,
              sys.argv[5].split(",") if len(sys.argv) > 5 else None)
