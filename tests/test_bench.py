"""Tests for bench.py: the evaluation matrix and --skip-existing."""

from invaders.__main__ import main
from invaders.bench import Game, build_matrix, existing_keys, game_key


def test_build_matrix_counts_games_for_two_players_two_modes_two_delays():
    games = build_matrix(
        players=["code", "random"], seeds=[1], modes=["turn", "realtime"], delays=[0, 250]
    )

    # code: 1 turn game + 2 realtime games (one per delay) = 3
    # random: 1 turn game + 1 realtime game (delays apply only to code) = 2
    # total = 5
    assert len(games) == 5
    assert games == [
        Game("code", "turn", 1, 0.0),
        Game("code", "realtime", 1, 0.0),
        Game("code", "realtime", 1, 250.0),
        Game("random", "turn", 1, 0.0),
        Game("random", "realtime", 1, 0.0),
    ]


def test_build_matrix_multiple_seeds_and_delays():
    games = build_matrix(players=["code"], seeds=[1, 2], modes=["realtime"], delays=[0, 50])

    assert len(games) == 4
    assert {g.seed for g in games} == {1, 2}
    assert {g.added_delay_ms for g in games} == {0.0, 50.0}


def test_skip_existing_skips_recorded_combinations():
    results = {
        "runs": [
            {
                "player": "code",
                "mode": "turn",
                "seed": 1,
                "added_delay_ms": 0.0,
                "max_steps": 20,
            }
        ],
        "baseline": {
            "runs": [
                {
                    "player": "llm",
                    "mode": "turn",
                    "seed": 5,
                    "added_delay_ms": 0.0,
                    "max_steps": 20,
                }
            ]
        },
    }
    existing = existing_keys(results)

    matrix = build_matrix(players=["code", "random"], seeds=[1, 2], modes=["turn"], delays=[0])
    remaining = [g for g in matrix if game_key(g, max_steps=20) not in existing]

    assert len(matrix) == 4
    assert len(remaining) == 3
    assert Game("code", "turn", 1, 0.0) not in remaining
    assert Game("code", "turn", 2, 0.0) in remaining
    assert Game("random", "turn", 1, 0.0) in remaining


def test_skip_existing_respects_max_steps():
    # Same (player, mode, seed, delay) recorded with a different max_steps must
    # not be treated as a match, since a shorter game is not comparable.
    results = {
        "runs": [
            {
                "player": "code",
                "mode": "turn",
                "seed": 1,
                "added_delay_ms": 0.0,
                "max_steps": 20,
            }
        ],
        "baseline": {"runs": []},
    }
    existing = existing_keys(results)

    matrix = build_matrix(players=["code"], seeds=[1], modes=["turn"], delays=[0])
    remaining = [g for g in matrix if game_key(g, max_steps=50) not in existing]

    assert remaining == matrix


def test_bench_command_plays_the_expected_games(capsys):
    # code,random over one seed, both modes, delays 0 and 250: same matrix as
    # test_build_matrix_counts_games_for_two_players_two_modes_two_delays (5
    # games). --no-commit and a small --max-steps keep this fast and offline.
    exit_code = main(
        [
            "bench",
            "--players",
            "code,random",
            "--seeds",
            "1",
            "--modes",
            "turn,realtime",
            "--delays",
            "0,250",
            "--max-steps",
            "20",
            "--no-commit",
        ]
    )

    out = capsys.readouterr().out
    assert exit_code == 0
    game_lines = [line for line in out.splitlines() if line.startswith("player=")]
    assert len(game_lines) == 5
    assert "ran 5 games, skipped 0 already recorded" in out


def test_new_player_version_is_not_skipped():
    game = Game("code", "turn", 101, 0.0)
    recorded = {"runs": [{"player": "code", "mode": "turn", "seed": 101,
                          "added_delay_ms": 0, "max_steps": None}],
                "baseline": {"runs": []}}
    existing = existing_keys(recorded)
    assert game_key(game, None) in existing  # v1 run, recorded without a version
    assert game_key(game, None, "v2") not in existing
    recorded["runs"][0]["player_version"] = "v2"
    assert game_key(game, None, "v2") in existing_keys(recorded)
