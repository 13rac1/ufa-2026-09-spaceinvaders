# Holding FIRE beat the AI

The [UFA JEV Bake-Off](https://ufa.foundation/jev/space-invaders/) (September 2026) asked builders
to play Atari Space Invaders with JEV, TypeSafe's new decision model, and compare it with an LLM.
The premise: "An LLM that takes two seconds to think is already dead. A decision model answers in
about the time one frame takes. Prove it." This is our entry (eval track): the same game, the same
seeds, every decision measured.

**The result:** a player that just holds FIRE outscored two LLMs (Claude Haiku 4.5,
Qwen3.8 27B) and matched JEV when each model chose every move from the game's facts. The Code Autopilot, a
rule-based player that runs no model while it plays, beat all three by more than ten times.
JEV still beat both LLMs: twice their score, 12x faster and 35x cheaper.

**The autopilot does not cheat.** It sees the same screen the models are told about (the
positions of the ship, aliens, bullets and shields) and, like any player, remembers what it
saw a moment ago. No hidden game memory, no seed, no look-ahead, no copy of the emulator. It
calculates where an alien will be when a shot arrives; the models have to guess.

**The explainer, with videos and a quiz:** https://13rac1.github.io/ufa-2026-09-spaceinvaders/

The reason is one setting most comparisons do not state: how much the harness works out
before the model decides. We call it the **input tier** and fix it per row:

- **Tier 1:** the game as positions (the organizers' recommended state).
- **Tier 2:** the same facts with distances and timings worked out.
- **Tier 3:** the autopilot's own verdicts (safe moves, target). The autopilot decides; a reference row.

## Results

Turn mode (the game waits for every decision), evaluation seeds 101-105, mean score.

| Player | Input | Score | Games | Time per decision | Cost per decision |
|---|---|---|---|---|---|
| Code Autopilot | its own rules | 3,180 | 5 | < 0.1 ms | $0 |
| JEV | Tier 3: code verdicts (reference) | 2,154 | 5 | 99 ms | $0.00006 |
| Always FIRE | none | 285 | 5 | < 0.1 ms | $0 |
| JEV | Tier 1 | 221 | 5 | 92 ms | $0.00004 |
| JEV | Tier 2 | 194 | 5 | 93 ms | $0.00004 |
| Qwen3.8 27B | Tier 2 | 185 | 2 | 2,293 ms | self-hosted, not counted |
| Random | none | 125 | 5 | < 0.1 ms | $0 |
| Qwen3.8 27B | Tier 1 | 113 | 5 | 2,441 ms | self-hosted, not counted |
| Haiku 4.5 | Tier 1 | 105 | 5 | 1,072 ms | $0.00139 |
| Haiku 4.5 | Tier 2 | 103 | 5 | 1,064 ms | $0.0014 |

**Realtime** (the game keeps running while the model thinks), same seeds: JEV at Tier 1 keeps
most of its score (198 against 221) at 92 ms per decision; the autopilot loses nothing (3,180).
During one Haiku decision (about 1.1 s) 64 frames pass.

**Holding FIRE scores 285 on every seed.** The game itself has no randomness; the seed only
decides when the environment repeats the previous action (sticky actions), and that cannot change
a player that always presses FIRE. Every other player's games vary around it: JEV at Tier 1 has
11 recorded games (seeds 101-110 and 119) from 105 to 660, and its mean over all 11 is 296, level
with holding FIRE. On the five table seeds JEV scores 221 and beats FIRE in two.

Human reference: 1,668.7. Over all 20 evaluation seeds the autopilot scores 2,682.

**The autopilot took many iterations to get this good:** five versions (891, 1,562, 2,306,
2,365, 2,682 on the evaluation seeds) and tens of thousands of practice games. An AI coding
agent (Claude) wrote and tuned it with the operator; every change was measured game by game
on two practice seed sets, and about a dozen ideas that did not hold were dropped.

## Finding

- **JEV against the LLMs:** at Tier 1, JEV scores 221 against 113 (Qwen) and 105 (Haiku),
  12x faster and 35x cheaper per decision than Haiku.
- **Choosing every move from facts, no model clearly beats holding FIRE (285).** The LLMs
  score less than half of it; JEV is level with it (221 on the table seeds, 296 over all 11 of
  its games). JEV fires every
  time the gun is ready, lined up or not, and rarely moves toward a target.
- **Fast enough to play, wrong for the task.** In realtime JEV keeps most of its score: it
  can play at game speed. But even when the game waits for it, it cannot work out where an
  alien will be when a shot arrives, so it plays like holding FIRE.
- **When the answer can be calculated from what is on the screen, the decision belongs in
  code.** JEV's own guide says
  the same: "Keep known rules, calculations, exact lookups, and execution in code."

## Limitations

- The autopilot was written and tuned by an AI coding agent (Claude) on practice seeds
  (1-99, 10000+); the table uses seeds from 101 only.
- Model answers are not exactly repeatable (JEV returns slightly different probabilities to
  the same request), so model games cannot be replayed; autopilot games replay exactly.
- The Tier 3 row is code-assisted by design: it shows what a model adds on top of the autopilot's verdicts.
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
