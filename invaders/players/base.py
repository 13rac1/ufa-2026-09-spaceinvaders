"""The interface that every player implements."""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class Decision:
    """One decision and what it cost.

    The harness measures latency itself; a player reports only what the API returns.
    """

    action: int  # index into invaders.state.ACTIONS
    confidence: float | None = None  # as the decider reports it; None if it has none
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    served_model: str | None = None  # the model id the API returned
    error_status: int | None = None  # HTTP status of a failed call
    retries: int = 0
    fallback: bool = False  # True when the previous action was held instead


class Player(Protocol):
    name: str  # for example "random", "code", "jev", "laya", "llm"
    provider: str  # "none", "typesafe", "laya", "anthropic", ...
    requested_model: str | None

    def reset(self, seed: int) -> None:
        """Start a new game."""

    def decide(self, state: dict, previous_action: int) -> Decision:
        """Choose the next action from the decoded state."""
