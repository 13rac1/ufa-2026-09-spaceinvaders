"""Tests for the tiered model request: sizes, exact Tier 2 values, no verdicts below Tier 3."""

import json

import pytest

from invaders.env import make_env
from invaders.question import build_questions, build_request_state
from invaders.state import ACTIONS, decode, tier2_view

VERDICT_KEYS = {"safe_left", "safe_stay", "safe_right", "aligned", "target_dx", "features"}
CHARS_PER_TOKEN = 1.67  # measured on JEV: 1,603 tokens for 2,673 characters
MAX_TOKENS = {1: 700, 2: 500}


def _real_decoded_state(steps: int = 0) -> dict:
    env = make_env()
    try:
        obs, info = env.reset(seed=1)
        previous, previous_frame = None, 0
        for _ in range(steps + 1):
            frame = info["episode_frame_number"]
            state = decode(obs, env.unwrapped.ale.getScreenRGB(), previous, frame - previous_frame)
            previous, previous_frame = state, frame
            obs, _r, _t, _tr, info = env.step(0)
        return state
    finally:
        env.close()


def _keys(value) -> set:
    if isinstance(value, dict):
        return set(value) | set().union(*(_keys(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(_keys(v) for v in value)) if value else set()
    return set()


@pytest.mark.parametrize("tier", [1, 2])
def test_tiers_below_3_carry_no_verdicts_and_stay_small(tier):
    request_state = build_request_state(_real_decoded_state(200), tier)
    assert not (_keys(request_state) & VERDICT_KEYS)
    encoded = json.dumps(request_state, separators=(",", ":"))
    assert len(encoded) / CHARS_PER_TOKEN <= MAX_TOKENS[tier]


def test_tier3_is_the_verdict_view():
    state = _real_decoded_state()
    assert build_request_state(state, 3)["features"] == state["features"]


def test_tier2_values_are_exact():
    state = {
        "ship_x": 41,
        "lives": 3,
        "features": {"can_fire": True},
        "alien_bullets": [{"x": 61, "y": 156}, {"x": 62, "y": 186}],
        "aliens": [{"x": 44, "y": 135}, {"x": 60, "y": 135}, {"x": 44, "y": 117}],
        "shields": [{"x0": 42, "x1": 49, "pixels": 100}],
        "fleet": {"dir": -1, "step": 1, "period": 32, "since_move": 0, "left": 3, "x": 42},
        "mothership": None,
    }
    view = tier2_view(state)
    assert view["room_to_move_px"] == {"left": 4, "right": 78}
    assert view["shield_above_ship"] is True  # the shot's column, 42, is under 42-49
    assert view["alien_bullets"][0] == {
        "lane": "right", "arrival": "soon", "dx": 20, "frames_to_ship_row": 21,
        "stopped_by_shield": False,
    }
    assert view["alien_bullets"][1]["arrival"] == "now"
    assert view["alien_bullets"][1]["frames_to_ship_row"] == 0
    # 25 frames of flight at 1/32 px per frame leftward: 44 -> 43.2, from shot column 42.
    assert [a["dx_at_shot_arrival"] for a in view["lowest_row_aliens"]] == [1, 17]
    assert [a["side"] for a in view["lowest_row_aliens"]] == ["over_ship", "right"]
    assert view["other_aliens"] == 1


@pytest.mark.parametrize("tier", [1, 2, 3])
def test_questions_options_are_exactly_the_six_actions(tier):
    action = build_questions(tier)["action"]
    assert action["type"] == "choice"
    assert action["instructions"]
    assert list(action["criteria"]) == list(ACTIONS)
