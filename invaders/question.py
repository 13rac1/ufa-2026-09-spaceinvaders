"""Build the question every model player asks, at a declared input tier.

The tier says how much the harness computes before the model decides (see
FAIR_EVALUATION.md):

- Tier 1: the decoded objects as absolute positions (the organizers' recommended state).
- Tier 2: the same facts with the arithmetic done exactly, relative to the ship.
- Tier 3: verdicts computed by the code player (safe moves, target, alignment) and the
  code player's rules in the criteria. A labelled reference row only: at this tier the
  code decides and the model looks up the answer.

JEV and the LLMs receive the same request at the same tier. Keep the wording here,
in one place.
"""

from invaders.state import ACTIONS, tier1_view, tier2_view

# The wording version per tier, recorded with each run so a score change can be told
# apart from a wording change. Tier 2 v7 is the v4 wording with the values of the v3 fleet
# model; Tier 3 v9 is the v2 wording over the code player's v4 verdicts.
QUESTION_VERSIONS = {1: 3, 2: 7, 3: 9}

_GAME = (
    "The ship is 7 px wide and moves 0.5 px per frame; one step is 4 frames. Its shot "
    "rises 2 px per frame, one shot at a time. Alien bullets fall 1 px per frame; a "
    "bullet that reaches the ship's rows (y 185-194) within 3 px of its center destroys "
    "it. Shields (y 157-174) stop shots and bullets. The game ends when the aliens reach "
    "the shields. Choose the ship's action for the next step."
)

INSTRUCTIONS = {
    1: (
        "Space Invaders, screen pixels, x to the right, y down. " + _GAME + " fleet_vx is "
        "the fleet's speed in px per frame; it turns at the screen edges."
    ),
    2: (
        "Space Invaders. Offsets are px, negative to the left. Bullet dx is from the "
        "ship's center; alien and mothership dx is from the shot's column at the moment "
        "a shot fired now would reach them. lane over_ship: the bullet is within the "
        "ship's width; side over_ship: a shot fired now reaches that alien. arrival: now "
        "0-8 frames, soon 9-30, far more. " + _GAME
    ),
}

CRITERIA = {
    "NOOP": "Stay in place; no shot.",
    "FIRE": "Stay in place and fire (only possible when gun_ready is true).",
    "RIGHT": "Move right 2 px; no shot.",
    "LEFT": "Move left 2 px; no shot.",
    "RIGHTFIRE": "Move right 2 px and fire.",
    "LEFTFIRE": "Move left 2 px and fire.",
}

# Tier 3: question v2, the code player's rules stated over its verdicts.
TIER3_INSTRUCTIONS = (
    "Choose the action for the ship in this Space Invaders frame. The features field "
    "holds the computed facts; use them first. Never move to a side whose safe_left or "
    "safe_right is false. Priority: 1) if safe_stay is false, dodge: go left when "
    "nearest_threat.dx >= 0 (the bullet is right of or above the ship) and safe_left is "
    "true, else go right if safe_right is true; 2) otherwise, if aligned is false, move "
    "toward the target (target_dx > 0: right, < 0: left) if that side is safe, else "
    "stay; 3) fire only when aligned is true and can_fire is true."
)

TIER3_CRITERIA = {
    "NOOP": (
        "Stay and do not fire. Right when safe_stay is true and there is nothing to do "
        "now: aligned is true but can_fire is false; or the side toward the target is "
        "not safe (target_dx > 0 with safe_right false, or target_dx < 0 with safe_left "
        "false); or target_dx is null. Also right when no move is safe."
    ),
    "FIRE": "Stay and fire: safe_stay is true, aligned is true, and can_fire is true.",
    "RIGHT": (
        "Move right without firing. Dodge: safe_stay is false, safe_right is true, and "
        "either nearest_threat.dx < 0 or safe_left is false. Or approach: safe_stay is "
        "true, aligned is false, target_dx > 0, and safe_right is true."
    ),
    "LEFT": (
        "Move left without firing. Dodge: safe_stay is false, safe_left is true, and "
        "nearest_threat.dx >= 0. Or approach: safe_stay is true, aligned is false, "
        "target_dx < 0, and safe_left is true."
    ),
    "RIGHTFIRE": (
        "Move right and fire: the dodge case of RIGHT holds, and aligned is true and "
        "can_fire is true."
    ),
    "LEFTFIRE": (
        "Move left and fire: the dodge case of LEFT holds, and aligned is true and "
        "can_fire is true."
    ),
}


def _tier3_view(state: dict) -> dict:
    return {
        "features": state["features"],
        "ship_x": state["ship_x"],
        "lives": state["lives"],
        "aliens_left": state["aliens_left"],
        "aliens": state["aliens"],
        "alien_bullets": state["alien_bullets"],
        "player_shot": {"x": state["player_shot_x"], "y": state["player_shot_y"]},
        "shields": state["shields"],
        "mothership": state["mothership"],
        "fleet_vx": state["fleet_vx"],
    }


def build_request_state(state: dict, tier: int) -> dict:
    """Return the decoded state as a model receives it at the given tier."""
    return {1: tier1_view, 2: tier2_view, 3: _tier3_view}[tier](state)


def build_questions(tier: int) -> dict:
    """Return the one "action" choice question; options are exactly state.ACTIONS."""
    if tier == 3:
        instructions, criteria = TIER3_INSTRUCTIONS, TIER3_CRITERIA
    else:
        instructions, criteria = INSTRUCTIONS[tier], CRITERIA
    return {
        "action": {
            "type": "choice",
            "instructions": instructions,
            "criteria": {name: criteria[name] for name in ACTIONS},
        }
    }


# Tier 2 v6: a stated goal, field definitions, and each action by its effect, as
# structured objects (JEV accepts objects for instructions and options). Options that do
# nothing in the current state are left out: a move into a wall, a shot while one flies.
V6_INSTRUCTIONS = {
    "goal": (
        "Score by shooting aliens, and keep the ship from being hit. A shot hits an alien "
        "only if the alien is in `aliens.over_ship`. A bullet whose lane is over_ship when "
        "it arrives destroys the ship."
    ),
    "fields": {
        "dx": "px from the ship, negative to the left; for aliens, where the alien will be "
        "when a shot fired now reaches its row",
        "lane": "where a bullet falls relative to the ship: left, over_ship, right",
        "arrival": "when a bullet reaches the ship's rows: now 0-8 frames, soon 9-30, far",
        "room_to_move_px": "px the ship can still move each way",
        "gun_ready": "a shot can be fired now; one shot flies at a time",
        "aliens_behind_shields": "a shot cannot reach these",
    },
}

_MOVE_EFFECT = {
    "stay": "The ship stays; every dx and lane stays the same.",
    "right": (
        "The ship moves 2 px right: every dx drops by 2, so aliens and bullets on the right "
        "come closer to over_ship and those on the left move away."
    ),
    "left": (
        "The ship moves 2 px left: every dx rises by 2, so aliens and bullets on the left "
        "come closer to over_ship and those on the right move away."
    ),
}
_FIRE_EFFECT = "A shot rises from the ship; it hits the alien in `aliens.over_ship`, if any."


def _allowed(view: dict) -> tuple[list[str], bool]:
    moves = ["stay"]
    if view["room_to_move_px"]["left"] > 0:
        moves.append("left")
    if view["room_to_move_px"]["right"] > 0:
        moves.append("right")
    return moves, view["gun_ready"]


def build_v6_questions(view: dict, split: bool) -> dict:
    """The Tier 2 v6 questions for a compact view: one six-way choice, or split in two.

    Split: a move question (left, stay, right) and, when the gun is ready, a fire
    question (yes, no). Each pair of answers is exactly one action; no priority applies.
    """
    moves, can_fire = _allowed(view)
    if split:
        questions = {
            "move": {
                "type": "choice",
                "instructions": {**V6_INSTRUCTIONS, "question": "Which way should the ship move now?"},
                "criteria": {m: {"effect": _MOVE_EFFECT[m]} for m in moves},
            }
        }
        if can_fire:
            questions["fire"] = {
                "type": "choice",
                "instructions": {**V6_INSTRUCTIONS, "question": "Should the ship fire now?"},
                "criteria": {
                    "yes": {"effect": _FIRE_EFFECT},
                    "no": {"effect": "No shot; the gun stays ready."},
                },
            }
        return questions
    options = {}
    for move in moves:
        name = {"stay": "NOOP", "left": "LEFT", "right": "RIGHT"}[move]
        options[name] = {"effect": _MOVE_EFFECT[move] + " No shot."}
        if can_fire:
            fire_name = {"stay": "FIRE", "left": "LEFTFIRE", "right": "RIGHTFIRE"}[move]
            options[fire_name] = {"effect": _MOVE_EFFECT[move] + " " + _FIRE_EFFECT}
    return {
        "action": {
            "type": "choice",
            "instructions": {**V6_INSTRUCTIONS, "question": "Which action should the ship take now?"},
            "criteria": options,
        }
    }


def split_answers_to_action(move: str, fire: str | None) -> str:
    """The one action that a move answer and a fire answer name together."""
    fires = fire == "yes"
    return {
        ("stay", False): "NOOP", ("stay", True): "FIRE",
        ("left", False): "LEFT", ("left", True): "LEFTFIRE",
        ("right", False): "RIGHT", ("right", True): "RIGHTFIRE",
    }[(move, fires)]
