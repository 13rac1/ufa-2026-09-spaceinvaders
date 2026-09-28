"""A player that picks a uniform random action."""

import numpy as np

from invaders.players.base import Decision
from invaders.state import ACTIONS


class RandomPlayer:
    """Chooses one of the legal actions uniformly at random."""

    name = "random"
    provider = "none"
    requested_model: str | None = None

    def __init__(self) -> None:
        self._rng: np.random.Generator | None = None

    def reset(self, seed: int) -> None:
        self._rng = np.random.default_rng(seed)

    def decide(self, state: dict, previous_action: int) -> Decision:
        assert self._rng is not None, "reset() must run before decide()"
        action = int(self._rng.integers(0, len(ACTIONS)))
        return Decision(action=action, model_calls=0, served_model="random-policy")
