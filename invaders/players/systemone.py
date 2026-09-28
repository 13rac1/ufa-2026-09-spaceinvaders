"""A player backed by a System One wire-protocol model: JEV or Laya."""

import os
import time

import httpx

from invaders.players.base import Decision
import json

from invaders.question import QUESTION_VERSIONS, build_questions, build_request_state
from invaders.state import ACTIONS

RETRY_STATUSES = (429, 529)
BACKOFF_BASE_S = 0.2
BACKOFF_MAX_S = 0.5


class MissingAPIKeyError(RuntimeError):
    """Raised at construction when a required API key environment variable is unset."""


def _backoff_s(retry_number: int) -> float:
    """Backoff before the given retry (1-based); sum stays under about 1 s."""
    return min(BACKOFF_BASE_S * 2 ** (retry_number - 1), BACKOFF_MAX_S)


class SystemOnePlayer:
    """Asks one "action" choice question over the System One wire protocol.

    Works for any server that implements POST <base_url>/v1/systemone with the
    JEV request and response shape, including Laya, which serves the same
    protocol.
    """

    def __init__(
        self,
        name: str,
        base_url: str,
        model: str,
        api_key_env: str | None,
        provider: str,
        confidence_threshold: float | None = None,
        timeout_s: float = 5.0,
        max_retries: int = 2,
        api_key_required: bool = True,
        transport: httpx.BaseTransport | None = None,
        tier: int = 2,
    ) -> None:
        if api_key_env and api_key_required and not os.environ.get(api_key_env):
            raise MissingAPIKeyError(
                f"the {name!r} player requires the {api_key_env} environment "
                "variable to be set"
            )
        self.name = name
        self.input_tier = tier
        self.question_version = QUESTION_VERSIONS[tier]
        self.version = f"q{self.question_version}"
        self.provider = provider
        self.requested_model = model
        self._base_url = base_url.rstrip("/")
        self._api_key_env = api_key_env
        self._confidence_threshold = confidence_threshold
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        # transport is a test seam (see httpx.MockTransport); production callers
        # leave it unset and get the real network.
        self._client = httpx.Client(transport=transport)

    def reset(self, seed: int) -> None:
        pass

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        api_key = os.environ.get(self._api_key_env) if self._api_key_env else None
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def decide(self, state: dict, previous_action: int) -> Decision:
        body = {
            "state": build_request_state(state, self.input_tier),
            "model": self.requested_model,
            "questions": build_questions(self.input_tier),
        }
        headers = self._headers()
        url = f"{self._base_url}/v1/systemone"

        retries = 0
        model_calls = 0
        error_status = None
        response = None
        while True:
            model_calls = 1  # one model call per decision; each extra attempt is a retry
            try:
                # Compact JSON: the model is billed per input token.
                response = self._client.post(
                    url,
                    content=json.dumps(body, separators=(",", ":")),
                    headers=headers,
                    timeout=self._timeout_s,
                )
            except httpx.HTTPError:
                error_status = None
                if retries >= self._max_retries:
                    return self._fallback(previous_action, model_calls, retries, error_status)
                retries += 1
                time.sleep(_backoff_s(retries))
                continue

            if response.status_code in RETRY_STATUSES and retries < self._max_retries:
                error_status = response.status_code
                retries += 1
                time.sleep(_backoff_s(retries))
                continue
            break

        if response.status_code != 200:
            return self._fallback(
                previous_action, model_calls, retries, response.status_code
            )

        try:
            data = response.json()
        except ValueError:  # a body that is not JSON, for example a proxy error page
            return self._fallback(previous_action, model_calls, retries, response.status_code)
        answer = data.get("answers", {}).get("action")
        if answer is None or answer.get("choice") not in ACTIONS:
            return self._fallback(previous_action, model_calls, retries, None)

        confidence = answer.get("answer_confidence", answer.get("confidence"))
        if self._confidence_threshold is not None and (
            confidence is None or confidence < self._confidence_threshold
        ):
            return self._fallback(
                previous_action, model_calls, retries, None, confidence=confidence
            )

        usage = data.get("usage", {})
        return Decision(
            action=ACTIONS.index(answer["choice"]),
            confidence=confidence,
            model_calls=model_calls,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            served_model=data.get("model"),
            retries=retries,
        )

    def _fallback(
        self,
        previous_action: int,
        model_calls: int,
        retries: int,
        error_status: int | None,
        confidence: float | None = None,
    ) -> Decision:
        return Decision(
            action=previous_action,
            confidence=confidence,
            model_calls=model_calls,
            error_status=error_status,
            retries=retries,
            fallback=True,
        )
