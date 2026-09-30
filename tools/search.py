"""Random search over the code player's constants, on tuning seeds only.

Search on seeds 10000-10199 (200 games per configuration), then confirm the best
configurations on seeds 1-99. Evaluation seeds (101 and up, below 10000) are never used.

Usage: python tools/search.py CONFIGS [PROCESSES]
"""

import os
import random
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import invaders.state as st  # noqa: E402
from invaders.diagnose import diagnose_game  # noqa: E402
from invaders.players.code_player import CodePlayer  # noqa: E402

SEARCH_SEEDS = list(range(10000, 10200))
CONFIRM_SEEDS = list(range(1, 100))
SPACE = {
    "ALIGNED_PX": [3, 4, 5],
    "HIT_MARGIN": [0, 1, 2],
    "HORIZON_FRAMES": [30, 40, 60],
    "MOTHERSHIP_SAFE_ROW_Y": [135, 145, 155, 165],
}


def _play(args):
    config, seed = args
    for name, value in config.items():
        setattr(st, name, value)
    return diagnose_game((CodePlayer, seed))["score"]


def score(pool, config, seeds):
    return float(np.mean(pool.map(_play, [(config, s) for s in seeds], chunksize=4)))


def main(count: int, processes: int) -> None:
    rng = random.Random(0)
    base = {name: getattr(st, name) for name in SPACE}
    configs = [base] + [{k: rng.choice(v) for k, v in SPACE.items()} for _ in range(count)]
    results = []
    with Pool(processes) as pool:
        for config in configs:
            mean = score(pool, config, SEARCH_SEEDS)
            results.append((mean, config))
            print(round(mean), config, flush=True)
        results.sort(key=lambda r: -r[0])
        print("== confirm the top 5 on seeds 1-99")
        for mean, config in results[:5]:
            print(round(mean), round(score(pool, config, CONFIRM_SEEDS)), config, flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else os.cpu_count())
