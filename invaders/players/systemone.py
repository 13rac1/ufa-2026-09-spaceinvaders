"""A player backed by a System One wire-protocol model (JEV)."""

import json
import os

import httpx

from invaders.players.base import Decision
from invaders.players.retry import (
    MAX_OUTAGE_S,
    TRANSIENT_STATUSES,
    TransientStatus,
    call_with_retry,
    status_of,
)
from invaders.question import QUESTION_VERSIONS, build_questions, build_request_state
from invaders.state import ACTIONS


class MissingAPIKeyError(RuntimeError):
    """Raised at construction when a required API key environment variable is unset."""


class SystemOnePlayer:
    """Asks one "action" choice question over the System One wire protocol.

    Works for any server that implements POST <base_url>/v1/systemone with the
    JEV request and response shape.
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
        max_outage_s: float = MAX_OUTAGE_S,
        transport: httpx.BaseTransport | None = None,
        tier: int = 2,
    ) -> None:
        if api_key_env and not os.environ.get(api_key_env):
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
        self._max_outage_s = max_outage_s
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
        data, model_calls, retries, error_status = self._ask(
            build_request_state(state, self.input_tier), build_questions(self.input_tier)
        )
        if data is None:
            return self._fallback(previous_action, model_calls, retries, error_status)
        answer = data.get("answers", {}).get("action")
        if answer is None or answer.get("choice") not in ACTIONS:
            return self._fallback(previous_action, model_calls, retries, None)

        confidence = answer.get("confidence")
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

    def _ask(self, request_state: dict, questions: dict) -> tuple[dict | None, int, int, int | None]:
        """Send one request; return (response JSON or None, model calls, retries, HTTP status)."""
        body = {"state": request_state, "model": self.requested_model, "questions": questions}
        headers = self._headers()
        url = f"{self._base_url}/v1/systemone"

        def post() -> httpx.Response:
            # Compact JSON: the model is billed per input token.
            response = self._client.post(
                url,
                content=json.dumps(body, separators=(",", ":")),
                headers=headers,
                timeout=self._timeout_s,
            )
            if response.status_code in TRANSIENT_STATUSES:
                raise TransientStatus(response.status_code)
            return response

        model_calls = 1  # one model call per request; each extra attempt is a retry
        try:
            response, retries = call_with_retry(post, max_outage_s=self._max_outage_s)
        except Exception as error:  # noqa: BLE001 - a failed call must not end the game
            # A permanent failure, or an outage longer than max_outage_s.
            return None, model_calls, 0, status_of(error)
        if response.status_code != 200:
            return None, model_calls, retries, response.status_code
        try:
            return response.json(), model_calls, retries, None
        except ValueError:  # a body that is not JSON, for example a proxy error page
            return None, model_calls, retries, response.status_code

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
