# Holding FIRE beat the AI

The [UFA JEV Bake-Off](https://ufa.foundation/jev/space-invaders/) (September 2026) asked builders
to play Atari Space Invaders with JEV, TypeSafe's new decision model, and compare it with an LLM.
The premise: "An LLM that takes two seconds to think is already dead. A decision model answers in
about the time one frame takes. Prove it." This is our entry (eval track): the same game, the same
seeds, every decision measured.

**The result:** a player that just holds FIRE outscored two LLMs (Claude Haiku 4.5,
Qwen3.8 27B) and matched JEV when each model chose every move from the game's facts. The Code
Autopilot, a rule-based player that runs no model while it plays, beat all three by more than 50
times. JEV still beat both LLMs: twice their score, 12x faster and 35x cheaper.

**The explainer, with the trailer and a quiz:** https://13rac1.github.io/ufa-2026-09-spaceinvaders/

## Results

Each row fixes the **input tier**: how much the harness works out before the model decides.

- **Tier 1:** the game as positions (the organizers' recommended state).
- **Tier 2:** the same facts with distances and timings worked out.
- **Tier 3:** the autopilot's own verdicts (safe moves, target). A reference row, code-assisted by design.

Turn mode (the game waits for every decision), evaluation seeds 101-105, mean score.

| Player | Input | Score | Games | Time per decision | Cost per decision |
|---|---|---|---|---|---|
| Code Autopilot | its own rules | 11,349 | 5 | < 0.1 ms | $0 |
| JEV | Tier 3: code verdicts (reference) | 2,154 | 5 | 99 ms | $0.00006 |
| Always FIRE | none | 285 | 5 | < 0.1 ms | $0 |
| JEV | Tier 1 | 221 | 5 | 92 ms | $0.00004 |
| JEV | Tier 2 | 194 | 5 | 93 ms | $0.00004 |
| Qwen3.8 27B | Tier 2 | 185 | 2 | 2,293 ms | self-hosted, not counted |
| Random | none | 125 | 5 | < 0.1 ms | $0 |
| Qwen3.8 27B | Tier 1 | 113 | 5 | 2,441 ms | self-hosted, not counted |
| Haiku 4.5 | Tier 1 | 105 | 5 | 1,072 ms | $0.00139 |
| Haiku 4.5 | Tier 2 | 103 | 5 | 1,064 ms | $0.0014 |

Human reference: 1,668.7. Holding FIRE scores 285 on every seed: the game has no randomness of its
own, and the seed only decides when the environment repeats the previous action (sticky actions),
which cannot change a player that always presses FIRE. JEV at Tier 1 has 12 recorded games (seeds
101-110, and 119 twice) from 105 to 660; its mean over all 12 is 289, level with holding FIRE.

## Finding

- **Choosing every move from facts, no model clearly beats holding FIRE.** JEV fires every time
  the gun is ready, lined up or not, and rarely moves toward a target.
- **Fast enough to play, wrong for the task.** In realtime (the game keeps running while the
  model thinks), JEV keeps most of its score (198 against 221 on the same seeds) and the autopilot
  loses nothing; 64 frames pass during one Haiku decision. But even when the game waits, JEV
  cannot work out where an alien will be when a shot arrives. The autopilot calculates it.
- **When the answer can be calculated from what is on the screen, the decision belongs in
  code.** JEV's own guide says the same: "Keep known rules, calculations, exact lookups, and
  execution in code."

## The Code Autopilot

It sees what the models are told (the positions of the ship, aliens, bullets and shields) and,
like any player, remembers what it saw a moment ago. No hidden game memory, no seed, no
look-ahead, no copy of the emulator. An AI coding agent (Claude) wrote it with the operator over
six versions and tens of thousands of practice games: 891, 1,562, 2,306, 2,365, 2,682 and 9,365
on the 20 evaluation seeds. Version 6 came after the entry lock, from watching version 5 lose on
evaluation seed 119 ([FAIR_EVALUATION.md](FAIR_EVALUATION.md)).

## Limitations

- Model answers are not exactly repeatable, so model games cannot be replayed; autopilot games
  replay exactly.
- Five games per row; single games vary a lot (see the dots on the site).

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export TYPESAFE_API_KEY=... ANTHROPIC_API_KEY=...       # for the JEV and Haiku rows
.venv/bin/python -m invaders bench --players code,jev-t1,llm-t1,always-fire \
    --seeds 101-105 --modes turn --max-cost-usd 5         # plays and records each game
.venv/bin/python -m invaders report --out report/        # rebuilds the tables
.venv/bin/python -m invaders verify                      # replays recorded autopilot games exactly
```

The Qwen rows (`qwen-t1`, `qwen-t2`) need an OpenAI-compatible server: set
`LLM_BASE_URL`, `LLM_PROVIDER=openai`, `LLM_MODEL` and `LLM_REASONING_EFFORT=none`.

How the comparison is kept fair: [FAIR_EVALUATION.md](FAIR_EVALUATION.md). License: AGPL-3.0.
