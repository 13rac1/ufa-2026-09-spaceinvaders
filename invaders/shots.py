"""Count the player's shots and how each one ended, from RAM[85] and the rewards.

RAM[85] is ABSENT when no shot is in flight and holds a SHOT_BLOCKED code while a shot
is stopped by a shield. A shot that ends with a reward hit an alien or the mothership;
one stopped by a shield went into a shield; any other end is a miss (it left the screen).
"""

from invaders.state import ABSENT, SHOT_BLOCKED


class ShotCounter:
    def __init__(self) -> None:
        self.shots = self.hits = self.into_shields = 0
        self._open = False

    def step(self, ram_before, ram_after, reward: float) -> None:
        """Update with one environment step: the RAM before and after it and its reward."""
        before, after = int(ram_before[85]), int(ram_after[85])
        if before == ABSENT and after != ABSENT:
            self.shots += 1
            self._open = True
        if not self._open:
            return
        if reward > 0:
            self.hits += 1
            self._open = False
        elif after in SHOT_BLOCKED:
            self.into_shields += 1
            self._open = False
        elif after == ABSENT:
            self._open = False  # left the screen: a miss

    def record(self) -> dict:
        misses = self.shots - self.hits - self.into_shields - int(self._open)
        return {
            "shots": self.shots,
            "shot_hits": self.hits,
            "shots_into_shields": self.into_shields,
            "shot_misses": misses,
            "hit_rate": round(self.hits / self.shots, 4) if self.shots else None,
        }
