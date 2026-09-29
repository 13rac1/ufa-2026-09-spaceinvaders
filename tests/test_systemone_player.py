"""Tests for SystemOnePlayer against a mocked System One HTTP endpoint."""

import httpx
import pytest

from invaders.players.systemone import MissingAPIKeyError, SystemOnePlayer
from invaders.state import ACTIONS

NOOP, FIRE, RIGHT, LEFT, RIGHTFIRE, LEFTFIRE = range(len(ACTIONS))


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    """Retries back off with sleep; the tests do not wait."""
    monkeypatch.setattr("invaders.players.retry.time.sleep", lambda seconds: None)

FAKE_STATE = {
    "ship_x": 60,
    "aliens": [{"x": 40, "y": 30}],
    "aliens_left": 30,
    "alien_bullets": [],
    "player_shot_y": None,
    "player_shot_x": None,
    "mothership": None,
    "fleet_vx": 0.0,
    "fleet": {"dir": 1, "step": 1, "period": 32, "since_move": 0, "left": 30, "x": 30},
    "shields": [],
    "lives": 3,
    "features": {
        "can_fire": True,
        "safe_left": True,
        "safe_stay": True,
        "safe_right": True,
        "target_dx": 0,
        "aligned": True,
        "under_shield": False,
        "target_behind_shield": False,
        "nearest_threat": None,
    },
}


def _choice_response(choice="FIRE", confidence=0.9, extra_answer=None, model="jev-1.13.0"):
    answer = {"type": "choice", "choice": choice, "confidence": confidence, "probabilities": {}}
    if extra_answer:
        answer.update(extra_answer)
    return {
        "model": model,
        "answers": {"action": answer},
        "usage": {"input_tokens": 100, "output_tokens": 10},
    }


def make_player(handler, **kwargs):
    transport = httpx.MockTransport(handler)
    kwargs.setdefault("name", "jev")
    kwargs.setdefault("base_url", "https://api.typesafe.ai")
    kwargs.setdefault("model", "jev-latest")
    kwargs.setdefault("api_key_env", None)
    kwargs.setdefault("provider", "typesafe")
    return SystemOnePlayer(transport=transport, **kwargs)


def test_missing_required_api_key_raises_before_any_request(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(MissingAPIKeyError, match="TYPESAFE_API_KEY"):
        SystemOnePlayer(
            name="jev",
            base_url="https://api.typesafe.ai",
            model="jev-latest",
            api_key_env="TYPESAFE_API_KEY",
            provider="typesafe",
        )


def test_successful_call_returns_mapped_action_and_usage():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/systemone"
        return httpx.Response(200, json=_choice_response(choice="FIRE", confidence=0.9))

    player = make_player(handler)
    decision = player.decide(state=FAKE_STATE, previous_action=NOOP)

    assert decision.action == FIRE
    assert decision.confidence == 0.9
    assert decision.model_calls == 1
    assert decision.retries == 0
    assert decision.input_tokens == 100
    assert decision.output_tokens == 10
    assert decision.served_model == "jev-1.13.0"
    assert decision.fallback is False
    assert decision.error_status is None


def test_rate_limit_then_success_counts_one_retry():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json=_choice_response(choice="LEFT"))

    player = make_player(handler, max_outage_s=5)
    decision = player.decide(state=FAKE_STATE, previous_action=NOOP)

    assert decision.action == LEFT
    assert decision.retries == 1
    assert decision.model_calls == 1
    assert decision.fallback is False


def test_permanent_failure_falls_back_to_previous_action_with_error_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(529, json={"error": "overloaded"})

    player = make_player(handler, max_outage_s=5)
    decision = player.decide(state=FAKE_STATE, previous_action=RIGHT)

    assert decision.fallback is True
    assert decision.action == RIGHT
    assert decision.error_status == 529
    assert decision.model_calls == 1


def test_unknown_option_falls_back():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_choice_response(choice="JUMP"))

    player = make_player(handler)
    decision = player.decide(state=FAKE_STATE, previous_action=LEFTFIRE)

    assert decision.fallback is True
    assert decision.action == LEFTFIRE
    assert decision.error_status is None


def test_low_confidence_falls_back():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_choice_response(choice="FIRE", confidence=0.4))

    player = make_player(handler, confidence_threshold=0.6)
    decision = player.decide(state=FAKE_STATE, previous_action=RIGHTFIRE)

    assert decision.fallback is True
    assert decision.action == RIGHTFIRE
    assert decision.confidence == 0.4


def test_network_error_retries_then_falls_back():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    player = make_player(handler, max_outage_s=5)
    decision = player.decide(state=FAKE_STATE, previous_action=FIRE)

    assert decision.fallback is True
    assert decision.action == FIRE
    assert decision.error_status is None
    assert decision.model_calls == 1


def test_bad_request_falls_back_without_retrying():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400, json={"error": "bad request"})

    player = make_player(handler, max_outage_s=5)
    decision = player.decide(state=FAKE_STATE, previous_action=FIRE)

    assert calls["n"] == 1
    assert decision.fallback is True
    assert decision.error_status == 400


def test_connection_drop_is_retried_until_it_returns():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] <= 4:
            raise httpx.ConnectError("no route to host", request=request)
        return httpx.Response(200, json=_choice_response(choice="LEFT"))

    player = make_player(handler, max_outage_s=600)
    decision = player.decide(state=FAKE_STATE, previous_action=FIRE)

    assert decision.action == LEFT
    assert decision.fallback is False
    assert decision.retries == 4
