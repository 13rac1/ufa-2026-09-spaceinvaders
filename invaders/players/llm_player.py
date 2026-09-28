"""The LLM baseline player: the organizers' required apples-to-apples comparison.

Runs the identical System One question through the System One adapter
(https://github.com/typesafe-ai/system-one-adapter-python), on the builder's own
provider key, instead of a hand-rolled LLM client.
"""

import os

from system_one_adapter import Choice, SystemOneAdapterClient
from typesafe_sdk import TypeSafeError

from invaders.players.base import Decision
from invaders.players.systemone import MissingAPIKeyError
from invaders.question import QUESTION_VERSIONS, build_questions, build_request_state
from invaders.state import ACTIONS

DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-haiku-4-5"

# The adapter needs a provider SDK's own key; it does not read a System One key.
PROVIDER_API_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


def _adapt_questions(questions: dict) -> dict:
    """Convert build_questions()'s wire-format dict into the adapter's Choice type."""
    return {
        name: Choice(instructions=q["instructions"], criteria=q["criteria"])
        for name, q in questions.items()
    }


class LLMPlayer:
    """Asks the same "action" question as SystemOnePlayer, through an LLM provider."""

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        confidence_threshold: float | None = None,
        tier: int = 2,
        name: str = "llm",
    ) -> None:
        self.name = name
        self.input_tier = tier
        self.question_version = QUESTION_VERSIONS[tier]
        self.version = f"q{self.question_version}"
        self.provider = provider or os.environ.get("LLM_PROVIDER", DEFAULT_PROVIDER)
        self.requested_model = model or os.environ.get("LLM_MODEL", DEFAULT_MODEL)
        self._confidence_threshold = confidence_threshold

        # A local OpenAI-compatible server (for example Qwen on our own GPU) needs no
        # hosted key: set LLM_BASE_URL, LLM_PROVIDER=openai and LLM_MODEL.
        self._base_url = os.environ.get("LLM_BASE_URL")
        self._model_arg = self.requested_model
        if self._base_url:
            if self.provider != "openai":
                raise ValueError("LLM_BASE_URL needs LLM_PROVIDER=openai")
            from system_one_adapter.providers.openai import OpenAIProvider

            self._model_arg = OpenAIProvider(
                self.requested_model,
                base_url=self._base_url,
                api_key=os.environ.get("OPENAI_API_KEY", "local"),
            )
            self.provider = "local"  # served on our own hardware; recorded as such
        else:
            api_key_env = PROVIDER_API_KEY_ENV.get(self.provider, "ANTHROPIC_API_KEY")
            if not os.environ.get(api_key_env):
                raise MissingAPIKeyError(
                    f"the 'llm' player requires the {api_key_env} environment "
                    f"variable to be set for provider {self.provider!r}"
                )

        self._client = SystemOneAdapterClient(
            structured_outputs=True,
            llm_answer_mode="probabilities",
        )

    def reset(self, seed: int) -> None:
        pass

    def decide(self, state: dict, previous_action: int) -> Decision:
        request_state = build_request_state(state, self.input_tier)
        questions = _adapt_questions(build_questions(self.input_tier))

        try:
            response = self._client.system_one(
                request_state,
                questions,
                provider=None if self._base_url else self.provider,
                model=self._model_arg,
            )
        except Exception as error:  # noqa: BLE001 - a failed call must not end the game
            # TypeSafeError carries the HTTP status; provider SDK and network errors
            # may not. Either way the previous action is held and counted.
            status = error.status if isinstance(error, TypeSafeError) else None
            return Decision(
                action=previous_action,
                model_calls=1,
                error_status=getattr(error, "status_code", status),
                fallback=True,
            )

        answer = response.answers.get("action")
        if answer is None or answer.choice not in ACTIONS:
            return Decision(
                action=previous_action,
                model_calls=1,
                served_model=response.model,
                fallback=True,
            )

        confidence = answer.confidence
        if (
            self._confidence_threshold is not None
            and confidence < self._confidence_threshold
        ):
            return Decision(
                action=previous_action,
                confidence=confidence,
                model_calls=1,
                served_model=response.model,
                fallback=True,
            )

        usage = response.usage
        return Decision(
            action=ACTIONS.index(answer.choice),
            confidence=confidence,
            model_calls=1,
            input_tokens=usage.input_tokens_total or 0,
            output_tokens=usage.output_tokens_total or 0,
            served_model=response.model,
            retries=usage.n_retries,
        )
