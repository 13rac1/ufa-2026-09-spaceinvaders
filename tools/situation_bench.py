"""Score JEV question variants on fixed game situations, without playing games.

States come from code-player games on tuning seeds. Each state is sent once per
variant. The code player's verdicts score the answers; they are never sent to JEV.

Usage: python tools/situation_bench.py collect STATES.json
       python tools/situation_bench.py score STATES.json v4,v6,v6split
"""

import json
import os
import random
import sys
from concurrent.futures import ThreadPoolExecutor

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from invaders.env import make_env  # noqa: E402
from invaders.players.code_player import choose  # noqa: E402
from invaders.question import (  # noqa: E402
    build_questions, build_request_state, build_v6_questions, split_answers_to_action,
)
from invaders.state import ACTIONS, SHIP_MIN_X, decode, tier2_compact_view  # noqa: E402

PER_KIND = 75
PRICE_PER_TOKEN = 0.042 / 1e6


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


def request(state: dict, variant: str) -> tuple[dict, dict]:
    if variant == "v4":
        return build_request_state(state, 2), build_questions(2)
    view = tier2_compact_view(state)
    return view, build_v6_questions(view, split=variant == "v6split")


def ask(client: httpx.Client, state: dict, variant: str) -> tuple[str | None, int]:
    view, questions = request(state, variant)
    body = {"state": view, "model": "jev-latest", "questions": questions}
    response = client.post(
        "https://api.typesafe.ai/v1/systemone",
        content=json.dumps(body, separators=(",", ":")),
        headers={"Authorization": f"Bearer {os.environ['TYPESAFE_API_KEY']}",
                 "Content-Type": "application/json"},
        timeout=10,
    )
    if response.status_code != 200:
        return None, 0
    data = response.json()
    answers = data["answers"]
    tokens = data.get("usage", {}).get("input_tokens", 0)
    if variant == "v6split":
        fire = answers.get("fire", {}).get("choice")
        return split_answers_to_action(answers["move"]["choice"], fire), tokens
    return answers["action"]["choice"], tokens


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


def score(path: str, variants: list[str]) -> None:
    states = json.load(open(path))
    with httpx.Client() as client, ThreadPoolExecutor(6) as pool:
        for variant in variants:
            total_tokens, line = 0, []
            for k, group in states.items():
                results = list(pool.map(lambda s: ask(client, s, variant), group))
                total_tokens += sum(t for _, t in results)
                answered = [(s, a) for s, (a, _) in zip(group, results) if a]
                rate = sum(correct(k, s, a) for s, a in answered) / max(len(answered), 1)
                line.append(f"{k} {rate:.2f} (n {len(answered)})")
            print(f"{variant}: " + ", ".join(line) + f"; ${total_tokens * PRICE_PER_TOKEN:.3f}")


if __name__ == "__main__":
    command, path = sys.argv[1], sys.argv[2]
    collect(path) if command == "collect" else score(path, sys.argv[3].split(","))
