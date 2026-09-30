# Fair evaluation

How this repository keeps the comparison between players fair, and how to check it.

**Same conditions.** `ALE/SpaceInvaders-v5` with its defaults (frameskip 4, sticky
actions 0.25). One decision per step. In turn mode the game waits for each decision.

**Same information.** Every player's input comes from one decoder (`invaders/state.py`).
It uses only what is drawn on the screen, plus game rules measured by watching (speeds,
turning points), listed in its docstring. RAM is read only where the Atari flickers, for
objects that are drawn. No player uses the seed, the game's random numbers, or a copy of
the emulator.

**Declared input tier.** Every model row states its tier (see the README). The models at
one tier receive the same request (`invaders/question.py`). The code player uses no
information beyond Tier 1. Tier 2 values come from the same fleet model the code player
uses. The Tier 3 row was recorded with the verdicts of code v3 (question v8).

**Separate seeds.** Tuning used seeds 1-99 and 10000+; the results use seeds from 101.

**Which games count.** Each game is committed to `results.json` when it ends. A model
game counts if fewer than 5% of its decisions fell back to holding the previous action.
Each row reports the latest version of its player that has recorded games
(`player_version`: the code version or the question version); games of earlier versions
are not in this repository. Model answers are not exactly repeatable, so model games
cannot be replayed; code games can.

**Check it yourself:**

1. `python -m invaders verify` replays every recorded code game; scores match exactly.
2. `python -m pytest -q` checks, among others, that Tier 1 and Tier 2 carry no verdicts.
3. `python -c "from invaders.question import build_questions; print(build_questions(2))"`
   prints the exact question a model receives.
