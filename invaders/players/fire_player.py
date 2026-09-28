"""A player that presses FIRE on every step: the floor a model row should beat.

It moves nowhere and fires whenever the gun is ready, so it scores when the fleet
passes over the ship's starting column.
"""

from invaders.players.base import Decision
from invaders.state import ACTIONS

FIRE = ACTIONS.index("FIRE")


class AlwaysFirePlayer:
    name = "always-fire"
    provider = "none"
    requested_model = None

    def reset(self, seed: int) -> None:
        pass

    def decide(self, state: dict, previous_action: int) -> Decision:
        return Decision(action=FIRE, served_model="always-fire")
