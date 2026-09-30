"""The LLM baseline player: the organizers' required apples-to-apples comparison.

Runs the identical System One question through the System One adapter
(https://github.com/typesafe-ai/system-one-adapter-python), on the builder's own
provider key, instead of a hand-rolled LLM client.
"""

import functools
import os

from system_one_adapter import Choice, SystemOneAdapterClient
from typesafe_sdk import RetryPolicy

from invaders.players.base import Decision
from invaders.players.retry import MAX_OUTAGE_S, call_with_retry, status_of
from invaders.players.systemone import MissingAPIKeyError
from invaders.question import (
    QUESTION_VERSIONS,
    STRATEGY_VERSIONS,
    build_questions,
    build_request_state,
)
from invaders.state import ACTIONS

DEFAULT_PROVIDER = "anthropic"
CALL_TIMEOUT_S = 30.0
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
        max_outage_s: float = MAX_OUTAGE_S,
        strategy: bool = False,
    ) -> None:
        self._max_outage_s = max_outage_s
        self.strategy = strategy
        self.name = name
        self.input_tier = tier
        self.question_version = (STRATEGY_VERSIONS if strategy else QUESTION_VERSIONS)[tier]
        self.version = f"q{self.question_version}"
        self.provider = provider or os.environ.get("LLM_PROVIDER", DEFAULT_PROVIDER)
        self.requested_model = model or os.environ.get("LLM_MODEL", DEFAULT_MODEL)
        self._confidence_threshold = confidence_threshold

        # A local OpenAI-compatible server (for example Qwen through Ollama) needs no
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
            self.provider = "local"  # a local server; recorded as such
            # Reasoning models (for example Qwen) think before answering unless told not
            # to. The adapter has no field for it, so pass it to its OpenAI client.
            effort = os.environ.get("LLM_REASONING_EFFORT")
            if effort:
                completions = self._model_arg._client.chat.completions
                completions.create = functools.partial(completions.create, reasoning_effort=effort)
                self.reasoning_effort = effort
        else:
            api_key_env = PROVIDER_API_KEY_ENV.get(self.provider, "ANTHROPIC_API_KEY")
            if not os.environ.get(api_key_env):
                raise MissingAPIKeyError(
                    f"the 'llm' player requires the {api_key_env} environment "
                    f"variable to be set for provider {self.provider!r}"
                )

        self._client = self._new_client()

    @staticmethod
    def _new_client() -> SystemOneAdapterClient:
        # The adapter's default is no time limit: a call on a broken connection waited
        # 369 s. A call that exceeds CALL_TIMEOUT_S fails and call_with_retry retries it.
        return SystemOneAdapterClient(
            structured_outputs=True,
            llm_answer_mode="probabilities",
            retry=RetryPolicy(max_retries=0, timeout=CALL_TIMEOUT_S),
        )

    def _rebuild_client(self, error: Exception) -> None:
        """After a failed connection, start from a fresh client and connection pool."""
        try:
            self._client.close()
        except Exception:  # noqa: BLE001 - the old client may already be unusable
            pass
        self._client = self._new_client()

    def reset(self, seed: int) -> None:
        pass

    def decide(self, state: dict, previous_action: int) -> Decision:
        request_state = build_request_state(state, self.input_tier)
        questions = _adapt_questions(build_questions(self.input_tier, self.strategy))

        def call():
            return self._client.system_one(
                request_state,
                questions,
                provider=None if self._base_url else self.provider,
                model=self._model_arg,
            )

        try:
            response, retries = call_with_retry(
                call, on_retry=self._rebuild_client, max_outage_s=self._max_outage_s
            )
        except Exception as error:  # noqa: BLE001 - a failed call must not end the game
            # A permanent failure, or an outage longer than max_outage_s: hold the
            # previous action and count it.
            return Decision(
                action=previous_action,
                model_calls=1,
                error_status=status_of(error),
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
            retries=usage.n_retries + retries,
        )
