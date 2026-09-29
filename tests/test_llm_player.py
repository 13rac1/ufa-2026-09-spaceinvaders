"""Tests for LLMPlayer with the System One adapter's client mocked at its boundary.

No test calls a real LLM provider: client.system_one() is replaced directly, the
same seam the adapter's own users mock against.
"""

from types import SimpleNamespace

import httpx2
import pytest
from typesafe_sdk import TypeSafeUnprocessableEntityError

from invaders.players.llm_player import LLMPlayer
from invaders.players.systemone import MissingAPIKeyError
from invaders.state import ACTIONS

NOOP, FIRE, RIGHT, LEFT, RIGHTFIRE, LEFTFIRE = range(len(ACTIONS))

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


def _usage(input_tokens_total=120, output_tokens_total=8, n_retries=0):
    return SimpleNamespace(
        input_tokens_total=input_tokens_total,
        output_tokens_total=output_tokens_total,
        n_retries=n_retries,
    )


def _response(choice="FIRE", confidence=0.85, model="claude-haiku-4-5", **usage_kwargs):
    answer = SimpleNamespace(choice=choice, confidence=confidence)
    return SimpleNamespace(answers={"action": answer}, model=model, usage=_usage(**usage_kwargs))


def make_player(monkeypatch, system_one_fn):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    player = LLMPlayer()
    monkeypatch.setattr(player._client, "system_one", system_one_fn)
    return player


def test_missing_api_key_raises_before_building_a_client(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(MissingAPIKeyError, match="ANTHROPIC_API_KEY"):
        LLMPlayer()


def test_successful_call_returns_mapped_action_and_usage(monkeypatch):
    player = make_player(monkeypatch, lambda *a, **kw: _response(choice="LEFT", confidence=0.85))
    decision = player.decide(state=FAKE_STATE, previous_action=NOOP)

    assert decision.action == LEFT
    assert decision.confidence == 0.85
    assert decision.model_calls == 1
    assert decision.input_tokens == 120
    assert decision.output_tokens == 8
    assert decision.served_model == "claude-haiku-4-5"
    assert decision.fallback is False


def test_adapter_error_falls_back_with_error_status(monkeypatch):
    def raise_error(*a, **kw):
        raise TypeSafeUnprocessableEntityError(422, {"error": "bad"}, httpx2.Headers({}))

    player = make_player(monkeypatch, raise_error)
    decision = player.decide(state=FAKE_STATE, previous_action=RIGHT)

    assert decision.fallback is True
    assert decision.action == RIGHT
    assert decision.error_status == 422


def test_unknown_option_falls_back(monkeypatch):
    player = make_player(monkeypatch, lambda *a, **kw: _response(choice="JUMP"))
    decision = player.decide(state=FAKE_STATE, previous_action=LEFTFIRE)

    assert decision.fallback is True
    assert decision.action == LEFTFIRE


def test_low_confidence_falls_back(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    player = LLMPlayer(confidence_threshold=0.6)
    monkeypatch.setattr(
        player._client, "system_one", lambda *a, **kw: _response(choice="FIRE", confidence=0.3)
    )
    decision = player.decide(state=FAKE_STATE, previous_action=RIGHTFIRE)

    assert decision.fallback is True
    assert decision.action == RIGHTFIRE
    assert decision.confidence == 0.3


def test_decide_sends_a_choice_question_named_action(monkeypatch):
    captured = {}

    def fake_system_one(state, questions, **kw):
        captured["state"] = state
        captured["questions"] = questions
        return _response()

    player = make_player(monkeypatch, fake_system_one)
    player.decide(state=FAKE_STATE, previous_action=NOOP)

    assert "action" in captured["questions"]
    assert captured["questions"]["action"].criteria.keys() == set(ACTIONS)


def test_local_endpoint_needs_no_hosted_key(monkeypatch):
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LLM_BASE_URL", "http://gpu-host:8000/v1")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "qwen")
    from system_one_adapter.providers.openai import OpenAIProvider

    from invaders.players.llm_player import LLMPlayer

    player = LLMPlayer()
    assert isinstance(player._model_arg, OpenAIProvider)
    assert player._model_arg.model_name == "qwen"


def test_timeout_without_status_falls_back(monkeypatch):
    """A timeout error has no status attribute; the game must continue."""
    from typesafe_sdk import TypeSafeError

    class Timeout(TypeSafeError):
        def __init__(self):
            Exception.__init__(self, "timed out")

    def raise_timeout(*args, **kwargs):
        raise Timeout()

    player = make_player(monkeypatch, raise_timeout)
    decision = player.decide(FAKE_STATE, previous_action=3)
    assert decision.action == 3 and decision.fallback and decision.error_status is None
