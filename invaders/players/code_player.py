"""The deterministic player: rules over the decoded features, no model."""

from invaders.players.base import Decision
from invaders.state import ACTIONS

NOOP, FIRE, RIGHT, LEFT, RIGHTFIRE, LEFTFIRE = range(len(ACTIONS))


class CodePlayer:
    name = "code"
    provider = "none"
    requested_model = None

    def reset(self, seed: int) -> None:
        pass

    def decide(self, state: dict, previous_action: int) -> Decision:
        return Decision(action=choose(state["features"]), served_model="deterministic-code")


def choose(f: dict) -> int:
    """Dodge first, then aim at the nearest alien column and fire."""
    # Firing into a shield wastes the shot, unless the target is behind one.
    fire = f["can_fire"] and (not f["under_shield"] or f["target_behind_shield"])
    dx = f["target_dx"] or 0

    if not f["safe_stay"]:
        # Move away from the nearest threat; the other side only if that is not safe.
        threat_dx = f["nearest_threat"]["dx"] if f["nearest_threat"] else 0
        order = (LEFT, RIGHT) if threat_dx >= 0 else (RIGHT, LEFT)
        for move in order:
            if f["safe_left" if move == LEFT else "safe_right"]:
                if fire and f["aligned"]:
                    return LEFTFIRE if move == LEFT else RIGHTFIRE
                return move
        return order[0]  # no safe move: moving away is still the best chance

    if f["aligned"]:
        return FIRE if fire else NOOP
    if dx > 0 and f["safe_right"]:
        return RIGHT
    if dx < 0 and f["safe_left"]:
        return LEFT
    return NOOP
