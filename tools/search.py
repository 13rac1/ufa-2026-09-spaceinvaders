"""Random search over decoder constants: search on seeds 1-60, confirm on 61-99."""
import sys, random, json, numpy as np
sys.path.insert(0, '.')
import invaders.state as st
from invaders.players.code_player import CodePlayer
from invaders.diagnose import diagnose

SPACE = {
    "ALIGNED_PX": [3, 4, 5],
    "MOTHERSHIP_SAFE_ROW_Y": [125, 135, 145, 155],
    "HIT_MARGIN": [1, 2, 3],
    "HORIZON_FRAMES": [30, 40, 60],
}
def run(cfg, seeds):
    for k, v in cfg.items(): setattr(st, k, v)
    rows = diagnose(CodePlayer, seeds)
    return float(np.mean([r["score"] for r in rows]))
rng = random.Random(0)
base = {k: getattr(st, k) for k in SPACE}
configs = [base] + [{k: rng.choice(v) for k, v in SPACE.items()} for _ in range(int(sys.argv[1]))]
seen, results = set(), []
for cfg in configs:
    key = tuple(sorted(cfg.items()))
    if key in seen: continue
    seen.add(key)
    m = run(cfg, list(range(1, 61)))
    results.append((m, cfg)); print(round(m), cfg, flush=True)
results.sort(key=lambda r: -r[0])
print("== confirm top 4 on seeds 61-99")
for m, cfg in results[:4]:
    print(round(m), round(run(cfg, list(range(61, 100)))), cfg, flush=True)
