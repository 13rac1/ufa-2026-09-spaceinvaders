"""Ask JEV four narrow questions per frame at Tier 1 and score each against the code.

One request per frame carries all four questions (they run in parallel and cannot see
each other). The code player's own calculations are the answer key; they are never sent.

Usage: python tools/narrow_questions.py STATES.json OUT.json [THREADS]
"""

import json
import os
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from invaders.players.systemone import SystemOnePlayer  # noqa: E402
from invaders.question import _GAME, build_request_state  # noqa: E402
from invaders.state import SHIP_TOP_Y, SHOT_OFFSET, _lead_x, _shot_victim  # noqa: E402

PRICE = 0.042 / 1e6
CONTEXT = (
    "Space Invaders, screen pixels, x to the right, y down. "
    + _GAME.replace(" Choose the ship's action for the next step.", "")
    + " fleet_vx is the fleet's speed in px per frame; it turns at the screen edges."
    " The gun fires from x = ship x + 1."
)

QUESTIONS = {
    "danger": {"type": "noul", "instructions": {"context": CONTEXT, "question":
        "If the ship stays where it is, will an alien bullet hit it?"}},
    "safe_side": {"type": "choice", "instructions": {"context": CONTEXT, "question":
        "If the ship moves one step (2 px), which directions are safe from alien bullets?"},
        "criteria": {"left": "Only moving left is safe.", "right": "Only moving right is safe.",
                     "both": "Both directions are safe.", "neither": "Neither direction is safe."}},
    "target_side": {"type": "choice", "instructions": {"context": CONTEXT, "question":
        "A shot hits the lowest alien of its column. Of those lowest aliens, take the one nearest "
        "the gun. When a shot fired now reaches that alien's row, where will the alien be?"},
        "criteria": {"left": "More than 4 px left of the gun.", "over": "Within 4 px of the gun.",
                     "right": "More than 4 px right of the gun."}},
    "hit_now": {"type": "noul", "instructions": {"context": CONTEXT, "question":
        "Would a shot fired now hit an alien? A shield directly above the ship stops it."}},
}


def truth(state: dict) -> dict:
    f, fleet = state["features"], state["fleet"]
    shot_x = state["ship_x"] + SHOT_OFFSET
    columns = {}
    for a in state["aliens"]:
        key = round((a["x"] - state["fleet_x"]) / 8)
        if key not in columns or a["y"] > columns[key]["y"]:
            columns[key] = a
    dxs = [_lead_x(a, fleet) - shot_x for a in columns.values()]
    dx = min(dxs, key=abs) if dxs else 0
    left, right = f["safe_left"], f["safe_right"]
    return {
        "danger": not f["safe_stay"],
        "safe_side": "both" if left and right else "left" if left else "right" if right else "neither",
        "target_side": "over" if abs(dx) <= 4 else "left" if dx < 0 else "right",
        "hit_now": not f["under_shield"] and _shot_victim(
            state["aliens"], fleet, {"x": shot_x, "y": SHIP_TOP_Y}) is not None,
    }


def main(path: str, out: str, threads: int) -> None:
    player = SystemOnePlayer(name="jev-narrow", base_url="https://api.typesafe.ai", model="jev-latest",
                             api_key_env="TYPESAFE_API_KEY", provider="typesafe", tier=1)
    frames = [(k, s) for k, group in json.load(open(path)).items() for s in group]

    def ask(item):
        k, s = item
        data, *_ = player._ask(build_request_state(s, 1), QUESTIONS)
        return k, truth(s), data

    with ThreadPoolExecutor(threads) as pool:
        results = list(pool.map(ask, frames))
    tokens, rows = 0, []
    for k, t, data in results:
        if not data:
            continue
        tokens += data.get("usage", {}).get("input_tokens", 0)
        a = data["answers"]
        rows.append({"kind": k, "truth": t, "answer": {
            q: (a[q]["noul"] if QUESTIONS[q]["type"] == "noul" else a[q]["choice"]) for q in QUESTIONS},
            "probabilities": {q: a[q].get("probabilities") for q in QUESTIONS if QUESTIONS[q]["type"] == "choice"}})
    json.dump(rows, open(out, "w"), indent=1)

    print(f"{len(rows)} of {len(frames)} frames answered; ${tokens * PRICE:.3f}")
    for q, spec in QUESTIONS.items():
        answers = [r["answer"][q] > 0.5 if spec["type"] == "noul" else r["answer"][q] for r in rows]
        truths = [r["truth"][q] for r in rows]
        right = sum(a == t for a, t in zip(answers, truths))
        common, n_common = Counter(truths).most_common(1)[0]
        line = f"{q:12s} right {right / len(rows):.0%}  (always '{common}': {n_common / len(rows):.0%})"
        if spec["type"] == "noul":
            yes = [r["answer"][q] for r in rows if r["truth"][q]]
            no = [r["answer"][q] for r in rows if not r["truth"][q]]
            line += f"  mean p(yes) when yes {sum(yes) / max(len(yes), 1):.2f}, when no {sum(no) / max(len(no), 1):.2f}"
        else:
            line += f"  answers {dict(Counter(answers))} truth {dict(Counter(truths))}"
        print(line)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 6)
