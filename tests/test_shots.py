import numpy as np

from invaders.harness import run_game
from invaders.players.code_player import CodePlayer
from invaders.shots import ShotCounter
from invaders.state import ABSENT, SHOT_BLOCKED


def ram(shot):
    r = np.zeros(128, dtype=np.uint8)
    r[85] = shot
    return r


def test_counts_a_hit_a_miss_and_a_shield():
    c = ShotCounter()
    c.step(ram(ABSENT), ram(90), 0)          # fired
    c.step(ram(90), ram(60), 10)             # hit
    c.step(ram(60), ram(ABSENT), 0)
    c.step(ram(ABSENT), ram(90), 0)          # fired
    c.step(ram(90), ram(ABSENT), 0)          # left the screen: miss
    c.step(ram(ABSENT), ram(SHOT_BLOCKED[0]), 0)  # fired into a shield
    assert c.record() == {"shots": 3, "shot_hits": 1, "shots_into_shields": 1,
                          "shot_misses": 1, "hit_rate": 0.3333}


def test_a_game_record_carries_the_shot_fields():
    record = run_game(CodePlayer(), seed=1, mode="turn", max_steps=400)
    assert record["shots"] == record["shot_hits"] + record["shots_into_shields"] + record["shot_misses"] or \
        record["shots"] == record["shot_hits"] + record["shots_into_shields"] + record["shot_misses"] + 1
    assert record["shot_hits"] > 0 and 0 < record["hit_rate"] <= 1
