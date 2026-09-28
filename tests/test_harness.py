"""Tests for the harness's step arithmetic and run records."""

import pytest

from invaders.harness import hold_steps, run_game
from invaders.players.random_player import RandomPlayer
from invaders.results import check_consistency


@pytest.mark.parametrize(
    "latency_ms,carried,expected_k,expected_carry",
    [
        (0, 0.0, 0, 0.0),
        (0.05, 0.0, 0, 0.003),
        (50, 0.0, 0, 3.0),
        (50, 3.0, 1, 2.0),
        (70, 0.0, 1, 0.2),
        (1000, 0.0, 15, 0.0),
    ],
)
def test_hold_steps(latency_ms, carried, expected_k, expected_carry):
    k, carry = hold_steps(latency_ms, carried)
    assert k == expected_k
    assert carry == pytest.approx(expected_carry, abs=1e-9)


def test_turn_mode_short_game_passes_consistency_check():
    player = RandomPlayer()
    record = run_game(player, seed=1, mode="turn", max_steps=20)

    assert record["steps"] == 20
    assert record["decisions"] == 20
    assert record["player"] == "random"
    assert record["mode"] == "turn"
    check_consistency(record)  # raises on failure


def test_realtime_mode_short_game_passes_consistency_check():
    player = RandomPlayer()
    record = run_game(player, seed=1, mode="realtime", added_delay_ms=50, max_steps=20)

    assert record["steps"] == 20
    assert record["decisions"] <= record["steps"]
    assert record["mode"] == "realtime"
    check_consistency(record)  # raises on failure


def test_realtime_mode_does_not_exceed_max_steps():
    player = RandomPlayer()
    record = run_game(player, seed=1, mode="realtime", added_delay_ms=1000, max_steps=10)

    assert record["steps"] <= 10


def test_random_player_reports_no_confidence():
    player = RandomPlayer()
    record = run_game(player, seed=1, mode="turn", max_steps=5)

    assert "mean_confidence" not in record
    assert "low_conf_rate" not in record


def test_unknown_mode_raises():
    player = RandomPlayer()
    with pytest.raises(ValueError):
        run_game(player, seed=1, mode="bogus", max_steps=1)


def test_video_and_log_output(tmp_path):
    player = RandomPlayer()
    video_path = tmp_path / "game.mp4"
    log_path = tmp_path / "game.jsonl"

    record = run_game(
        player,
        seed=1,
        mode="turn",
        max_steps=10,
        record_video=str(video_path),
        log_path=str(log_path),
    )

    assert video_path.exists() and video_path.stat().st_size > 0
    assert log_path.exists()
    lines = log_path.read_text().splitlines()
    assert len(lines) == record["decisions"]
