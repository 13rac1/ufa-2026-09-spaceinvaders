import json

import httpx
import pytest

from invaders.env import make_env
from invaders.players.goal_player import RULES, GoalPlayer
from invaders.state import decode


@pytest.fixture(scope="module")
def state():
    env = make_env()
    obs, _ = env.reset(seed=2)
    for _ in range(60):
        obs, *_ = env.step(1)
    decoded = decode(obs, env.unwrapped.ale.getScreenRGB(), None, 4)
    env.close()
    return decoded


def make_player(handler, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test")
    return GoalPlayer(name="jev-goal", base_url="https://example.test", model="jev-latest",
                      api_key_env="TYPESAFE_API_KEY", provider="typesafe",
                      transport=httpx.MockTransport(handler))


def answering(rule):
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        letter = next(k for k, o in body["state"]["options"].items() if o["rule"] == RULES[rule])
        return httpx.Response(200, json={"answers": {"target": {"type": "choice", "choice": letter,
                                                               "confidence": 0.9}},
                                         "usage": {"input_tokens": 10, "output_tokens": 2},
                                         "model": "jev-1.13.0"})
    return handler, requests


def test_asks_once_and_follows_the_chosen_rule(state, monkeypatch):
    handler, requests = answering("left_edge")
    player = make_player(handler, monkeypatch)
    first = player.decide(state, 0)
    second = player.decide(state, first.action)
    assert len(requests) == 1 and first.model_calls == 1 and second.model_calls == 0
    assert player._rule == "left_edge" and not first.fallback
    assert set(requests[0]["questions"]["target"]["criteria"]) == set(requests[0]["state"]["options"])


def test_asks_again_after_a_kill(state, monkeypatch):
    handler, requests = answering("nearest")
    player = make_player(handler, monkeypatch)
    player.decide(state, 0)
    player.decide({**state, "aliens_left": state["aliens_left"] - 1}, 0)
    assert len(requests) == 2


def test_an_unknown_answer_falls_back_to_the_code_players_target(state, monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"answers": {"target": {"choice": "Z"}}})
    player = make_player(handler, monkeypatch)
    decision = player.decide(state, 0)
    assert decision.fallback and player._rule is None
