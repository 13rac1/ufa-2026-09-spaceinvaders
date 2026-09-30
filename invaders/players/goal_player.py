"""JEV chooses the target rule, code executes: the "select instead of generate" pattern.

Code lists the target rules it can execute (the left or right edge column, whichever
edge column is closer, the lowest row, the nearest alien, the mothership), each with
exact facts about the alien it would aim at now. JEV makes one choice. Code applies that
rule every step (the fleet moves, so the rule's alien changes), moves the ship, aims,
fires and dodges with the code player's rules (choose()), and asks again after each kill
or when the mothership appears or leaves. JEV gets no verdict on which rule is best.
"""

import string

from invaders.players.base import Decision
from invaders.players.code_player import choose
from invaders.players.llm_player import LLMPlayer
from invaders.players.retry import call_with_retry, status_of
from invaders.players.systemone import SystemOnePlayer
from invaders.state import (
    ALIGNED_PX,
    MOTHERSHIP_Y,
    SHIP_MAX_X,
    SHIP_MIN_X,
    SHIP_TOP_Y,
    SHOT_OFFSET,
    SHOT_SPEED,
    _frames_to_invasion,
    _lead_x,
)

GOAL_VERSION = "g1"
ROW_POINTS = (5, 10, 15, 20, 25, 30)  # from the bottom row up

RULES = {
    "left_edge": "The lowest alien of the leftmost column.",
    "right_edge": "The lowest alien of the rightmost column.",
    "nearer_edge": "The lowest alien of whichever edge column is closer to the gun.",
    "lowest_row": "The alien of the lowest row that is closest to the gun.",
    "nearest": "The alien a shot can reach soonest, in any column.",
    "mothership": "The mothership crossing the top of the screen.",
}

INSTRUCTIONS = {
    "task": (
        "Space Invaders. Choose which target rule the ship follows until the next alien "
        "is destroyed. Code applies the rule every step, moves the ship, aims, fires and "
        "dodges bullets."
    ),
    "rules": (
        "A shot always hits the lowest alien of its column. The fleet moves sideways and "
        "drops 10 px each time its outermost column reaches a screen edge. The game ends "
        "when the lowest aliens reach y 160. A fleet with fewer columns travels further "
        "between drops. The fleet speeds up as aliens are destroyed. The ship moves 2 px "
        "per step; a shot rises 2 px per frame. Clearing all aliens starts a new wave at "
        "the top."
    ),
}


def _shield_columns(state: dict) -> set[int]:
    return {x for s in state["shields"] for x in range(s["x0"], s["x1"] + 1)}


def _targets(state: dict) -> dict[str, dict]:
    """The alien (or mothership) each rule aims at now, with its facts."""
    aliens, fleet = state["aliens"], state["fleet"]
    shot_x = state["ship_x"] + SHOT_OFFSET
    shields = _shield_columns(state)
    columns: dict[int, list[dict]] = {}
    for a in aliens:
        columns.setdefault(round((a["x"] - state["fleet_x"]) / 8), []).append(a)
    lowest = {k: max(c, key=lambda a: a["y"]) for k, c in columns.items()}
    rows = sorted({round(a["y"] / 6) for a in aliens}, reverse=True)  # bottom first

    def reachable(a):
        return SHIP_MIN_X <= a["x"] - SHOT_OFFSET <= SHIP_MAX_X and round(a["x"]) not in shields

    def dx(a):
        return round(_lead_x(a, fleet) - shot_x)

    def target(a, key):
        return {"dx": dx(a), "kind": "alien", "behind_shield": round(a["x"]) in shields,
                "facts": {"dx_px": dx(a), "steps_to_align": abs(dx(a)) // 2,
                          "points": ROW_POINTS[min(rows.index(round(a["y"] / 6)), 5)],
                          "aliens_in_its_column": len(columns[key]),
                          "shot_flight_frames": round((SHIP_TOP_Y - a["y"]) / SHOT_SPEED),
                          "behind_shield": round(a["x"]) in shields}}

    out = {}
    if lowest:
        keys = sorted(lowest)
        left, right = keys[0], keys[-1]
        out["left_edge"] = target(lowest[left], left)
        out["right_edge"] = target(lowest[right], right)
        low_y = max(a["y"] for a in aliens)
        bottom = [k for k in keys if lowest[k]["y"] >= low_y - 2]
        clear = [k for k in bottom if reachable(lowest[k])] or bottom
        k = min(clear, key=lambda k: abs(dx(lowest[k])))
        out["lowest_row"] = target(lowest[k], k)
        # With neither edge column clear, the code player's fallback: the lowest row.
        edges = [k for k in {left, right} if reachable(lowest[k])] or clear
        near = min(edges, key=lambda k: abs(dx(lowest[k])))
        out["nearer_edge"] = target(lowest[near], near)
        clear = [k for k in keys if reachable(lowest[k])] or keys
        k = min(clear, key=lambda k: abs(dx(lowest[k])) / 2 + (SHIP_TOP_Y - lowest[k]["y"]) / SHOT_SPEED)
        out["nearest"] = target(lowest[k], k)
    ship = state["mothership"]
    if ship is not None and ship.get("vx"):
        lead = ship["x"] + ship["vx"] * (SHIP_TOP_Y - MOTHERSHIP_Y) / SHOT_SPEED
        d = round(lead - shot_x)
        if SHIP_MIN_X <= lead - SHOT_OFFSET <= SHIP_MAX_X:
            out["mothership"] = {"dx": d, "kind": "mothership", "behind_shield": False,
                                 "facts": {"dx_px": d, "steps_to_align": abs(d) // 2,
                                           "points": 200}}
    return out


def request_state(state: dict, targets: dict[str, dict], ids: dict[str, str]) -> dict:
    lowest_y = max((a["y"] for a in state["aliens"]), default=0)
    return {
        "aliens_left": state["aliens_left"],
        "columns_left": len({round((a["x"] - state["fleet_x"]) / 8) for a in state["aliens"]}),
        "lowest_row_y": lowest_y,
        "frames_until_invasion": round(_frames_to_invasion(lowest_y, state["fleet"])),
        "fleet_direction": "right" if state["fleet"]["dir"] > 0 else "left",
        "options": {letter: {"rule": RULES[rule], **targets[rule]["facts"]}
                    for letter, rule in ids.items()},
    }


def question(ids: dict[str, str]) -> dict:
    return {
        "target": {
            "type": "choice",
            "instructions": INSTRUCTIONS,
            "criteria": {letter: f"Follow `options.{letter}`: {RULES[rule]}"
                         for letter, rule in ids.items()},
        }
    }


class GoalMixin:
    """The model picks the target rule; the code player's rules execute it.

    The concrete player supplies _ask(request_state, questions), returning
    (response dict or None, model calls, retries, HTTP status).
    """

    def _init_goal(self) -> None:
        self.input_tier = "goal"
        self.version = GOAL_VERSION
        self.question_version = GOAL_VERSION
        self._rule = None
        self._asked_at = None  # (aliens_left, mothership on screen) when last asked

    def reset(self, seed: int) -> None:
        self._rule, self._asked_at = None, None

    def decide(self, state: dict, previous_action: int) -> Decision:
        targets = _targets(state)
        situation = (state["aliens_left"], "mothership" in targets)
        decision = Decision(action=0)
        if targets and (situation != self._asked_at or self._rule not in targets):
            ids = dict(zip(string.ascii_uppercase, targets))
            data, calls, retries, status = self._ask(request_state(state, targets, ids), question(ids))
            answer = (data or {}).get("answers", {}).get("target") or {}
            usage = (data or {}).get("usage", {})
            self._rule = ids.get(answer.get("choice"))
            self._asked_at = situation
            decision = Decision(
                action=0,
                confidence=answer.get("confidence"),
                model_calls=calls,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                served_model=(data or {}).get("model"),
                error_status=status,
                retries=retries,
                fallback=self._rule is None,
            )
        features = dict(state["features"])  # without a rule: the code player's own target
        current = targets.get(self._rule)
        if current is not None:
            features.update(
                target_dx=current["dx"],
                target_kind=current["kind"],
                aligned=abs(current["dx"]) <= ALIGNED_PX,
                target_behind_shield=current["behind_shield"],
            )
        decision.action = choose(features)
        return decision


class GoalPlayer(GoalMixin, SystemOnePlayer):
    """JEV picks the target rule over the System One protocol."""

    def __init__(self, **kwargs) -> None:
        SystemOnePlayer.__init__(self, **kwargs)
        self._init_goal()


class LLMGoalPlayer(GoalMixin, LLMPlayer):
    """An LLM picks the target rule through the System One adapter: the same question."""

    def __init__(self, **kwargs) -> None:
        LLMPlayer.__init__(self, **kwargs)
        self._init_goal()

    def _ask(self, request_state: dict, questions: dict):
        from system_one_adapter import Choice

        adapted = {k: Choice(instructions=q["instructions"], criteria=q["criteria"])
                   for k, q in questions.items()}

        def call():
            return self._client.system_one(
                request_state, adapted,
                provider=None if self._base_url else self.provider, model=self._model_arg,
            )

        try:
            response, retries = call_with_retry(
                call, on_retry=self._rebuild_client, max_outage_s=self._max_outage_s
            )
        except Exception as error:  # noqa: BLE001 - a failed call must not end the game
            return None, 1, 0, status_of(error)
        answer = response.answers.get("target")
        usage = response.usage
        return {
            "answers": {"target": {"choice": answer.choice, "confidence": answer.confidence}}
            if answer is not None else {},
            "usage": {"input_tokens": usage.input_tokens_total or 0,
                      "output_tokens": usage.output_tokens_total or 0},
            "model": response.model,
        }, 1, retries + (usage.n_retries or 0), None
