"""Decode the game state into JSON-ready data.

Every player receives the same state from decode(). The harness calls it once per
decision with the 128-byte RAM and the RGB screen.

The Atari draws the player's shot and the alien bullets on alternate frames, and with
frameskip 4 every observed screen has the same parity: the alien bullets are never on
it. Moving objects therefore come from RAM, which does not flicker. The aliens and the
shields are drawn on every frame and come from the screen.

RAM addresses and screen geometry were measured with ale-py 0.12.1 (frameskip 1,
correlation of RAM bytes with screen positions):

- ship center x = RAM[28] + 2, range 37 to 119; moves 0.5 pixels per frame (2 per step).
- alien bullet 1: top y = 2 * RAM[81] + 6, x = RAM[83] - 2; RAM[81] == 246 when absent.
- alien bullet 2: top y = 2 * RAM[82] + 4, x = RAM[84] - 2; RAM[82] == 246 when absent.
- alien bullets are 1 pixel wide, 8 pixels tall, and fall about 1 pixel per frame.
- player shot: top y = 2 * RAM[85] + 4; RAM[85] == 246 when no shot is in flight. The
  shot leaves one pixel right of the ship's center.
- RAM[17]: aliens left. RAM[73]: lives. RAM[26]: fleet x (moves 1 pixel per move
  with a full fleet, faster as aliens die; no RAM byte holds the direction, so the
  velocity is estimated from the previous decoded state).
- ship rows y 185 to 194; shields y 157 to 174; aliens 8 by 10 pixels.
"""

import numpy as np

# Action indices of ALE/SpaceInvaders-v5 with the minimal action set.
ACTIONS = ("NOOP", "FIRE", "RIGHT", "LEFT", "RIGHTFIRE", "LEFTFIRE")

ABSENT = 246
SHIP_MIN_X, SHIP_MAX_X = 37, 119
SHIP_TOP_Y = 185
SHIP_BOTTOM_Y = 194
SHIP_HALF_WIDTH = 3  # the ship is 7 pixels wide
SHIP_SPEED = 0.5  # pixels per frame
SHOT_OFFSET = 1  # the shot's x is the ship's center plus this
SHOT_SPEED = 2.0  # pixels per frame, upward
VELOCITY_SMOOTHING = 0.7  # weight of the previous fleet velocity estimate
SHIELD_TOP_Y, SHIELD_BOTTOM_Y = 157, 174
BULLET_HEIGHT = 8
BULLET_SPEED = 1.0  # pixels per frame
FRAMES_PER_STEP = 4
HIT_MARGIN = 2  # extra pixels on each side of the ship when testing for a hit
ALIGNED_PX = 1  # fire only when the target's center is this close to the ship's
HORIZON_FRAMES = 40  # bullets further away than this are not a threat yet

ALIEN_COLOR = (134, 134, 29)
SHIELD_COLOR = (181, 83, 40)


def _runs(indices: np.ndarray) -> list[tuple[int, int]]:
    """Group sorted indices into (first, last) runs of consecutive values."""
    if len(indices) == 0:
        return []
    breaks = np.where(np.diff(indices) > 1)[0] + 1
    return [(int(r[0]), int(r[-1])) for r in np.split(indices, breaks)]


def _aliens(screen: np.ndarray) -> list[dict]:
    """Find each alien as the center of one sprite on the screen."""
    mask = (screen[20:SHIP_TOP_Y] == ALIEN_COLOR).all(-1)
    aliens = []
    for y0, y1 in _runs(np.where(mask.any(1))[0]):
        for x0, x1 in _runs(np.where(mask[y0 : y1 + 1].any(0))[0]):
            aliens.append({"x": (x0 + x1) // 2, "y": (y0 + y1) // 2 + 20})
    return aliens


def _shields(screen: np.ndarray) -> tuple[list[dict], np.ndarray]:
    """Return the shields and a per-column flag: True where a shield still stands."""
    mask = (screen[SHIELD_TOP_Y : SHIELD_BOTTOM_Y + 1] == SHIELD_COLOR).all(-1)
    columns = mask.any(0)
    shields = [
        {"x0": x0, "x1": x1, "pixels": int(mask[:, x0 : x1 + 1].sum())}
        for x0, x1 in _runs(np.where(columns)[0])
    ]
    return shields, columns


def _alien_bullets(ram: np.ndarray) -> list[dict]:
    """Alien bullets whose top is above the ship's bottom row.

    A slot keeps counting down past the ground after its bullet is gone, so a bullet
    below the ship's bottom row is stale. A bullet inside the ship's rows is real: the
    ship must not move into it.
    """
    bullets = []
    for y_addr, x_addr, y_offset in ((81, 83, 6), (82, 84, 4)):
        if ram[y_addr] != ABSENT:
            y = 2 * int(ram[y_addr]) + y_offset
            if y <= SHIP_BOTTOM_Y:
                bullets.append({"x": int(ram[x_addr]) - 2, "y": y})
    return bullets


def _frames_to_ship(bullet: dict) -> float:
    """Frames until the bottom of the bullet reaches the top of the ship."""
    return max(0.0, (SHIP_TOP_Y - (bullet["y"] + BULLET_HEIGHT)) / BULLET_SPEED)


def _blocked(bullet: dict, shield_columns: np.ndarray) -> bool:
    """True when a shield stands between the bullet and the ship."""
    return bullet["y"] + BULLET_HEIGHT < SHIELD_TOP_Y and bool(shield_columns[bullet["x"]])


def _hits(bullet: dict, ship_x: int, direction: int) -> bool:
    """True when the bullet hits a ship that moves in the direction (-1, 0, 1)."""
    t_enter = _frames_to_ship(bullet)
    if t_enter > HORIZON_FRAMES:
        return False
    # The bullet overlaps the ship rows for about 18 frames; check each of them.
    for t in range(int(t_enter), int(t_enter) + 18):
        x = min(max(ship_x + direction * SHIP_SPEED * t, SHIP_MIN_X), SHIP_MAX_X)
        if abs(bullet["x"] - x) <= SHIP_HALF_WIDTH + HIT_MARGIN:
            return True
    return False


def _lead_x(alien: dict, fleet_vx: float) -> float:
    """Where the alien will be when a shot fired now reaches its row."""
    return alien["x"] + fleet_vx * (SHIP_TOP_Y - alien["y"]) / SHOT_SPEED


def _features(ship_x, can_fire, aliens, bullets, shield_columns, fleet_vx) -> dict:
    shot_x = ship_x + SHOT_OFFSET
    threats = [b for b in bullets if not _blocked(b, shield_columns)]
    safe = {
        name: not any(_hits(b, ship_x, d) for b in threats)
        for name, d in (("left", -1), ("stay", 0), ("right", 1))
    }
    # Target: the game ends when the lowest alien row reaches the shields, so aim at
    # the lowest row first; those shots are also the shortest. Within that row, the
    # closest alien the ship can shoot without a shield in the way; if all of them are
    # behind a shield, the closest one.
    target_dx = None
    target_behind_shield = False
    if aliens:
        lowest_y = max(a["y"] for a in aliens)
        bottom_row = [a for a in aliens if a["y"] >= lowest_y - 2]
        clear = [
            a for a in bottom_row
            if SHIP_MIN_X <= a["x"] - SHOT_OFFSET <= SHIP_MAX_X and not shield_columns[a["x"]]
        ]
        target_behind_shield = not clear
        nearest = min(clear or bottom_row, key=lambda a: abs(_lead_x(a, fleet_vx) - shot_x))
        target_dx = round(_lead_x(nearest, fleet_vx) - shot_x)
    nearest_threat = None
    if threats:
        b = min(threats, key=_frames_to_ship)
        nearest_threat = {"dx": b["x"] - ship_x, "frames_to_ship": round(_frames_to_ship(b))}
    return {
        "can_fire": can_fire,
        "safe_left": safe["left"],
        "safe_stay": safe["stay"],
        "safe_right": safe["right"],
        "target_dx": target_dx,
        "aligned": target_dx is not None and abs(target_dx) <= ALIGNED_PX,
        "under_shield": bool(shield_columns[shot_x]),
        "target_behind_shield": target_behind_shield,
        "nearest_threat": nearest_threat,
    }


def _fleet_vx(fleet_x: int, previous: dict | None, frames_elapsed: int) -> float:
    """Estimate the fleet's horizontal velocity in pixels per frame.

    The fleet moves in jumps, so one decision often sees no change. The estimate
    averages over decisions and restarts when the direction changes.
    """
    if previous is None or frames_elapsed <= 0:
        return 0.0
    old_vx = previous["fleet_vx"]
    dx = fleet_x - previous["fleet_x"]
    if abs(dx) > 16:  # a new wave or a reset, not movement
        return 0.0
    instant = dx / frames_elapsed
    if dx != 0 and old_vx != 0 and (dx > 0) != (old_vx > 0):
        return instant  # the fleet turned at an edge
    return VELOCITY_SMOOTHING * old_vx + (1 - VELOCITY_SMOOTHING) * instant


def decode(
    ram: np.ndarray,
    screen: np.ndarray,
    previous: dict | None = None,
    frames_elapsed: int = FRAMES_PER_STEP,
) -> dict:
    """Return the game state as a dict of plain JSON types.

    ram: uint8 array of shape (128,). screen: uint8 array of shape (210, 160, 3).
    previous: the state decode() returned for the previous decision, used to estimate
    the fleet's velocity; frames_elapsed: frames since that decision.
    Positions are screen pixels; x grows to the right, y grows down.
    """
    ship_x = min(max(int(ram[28]) + 2, SHIP_MIN_X), SHIP_MAX_X)
    can_fire = ram[85] == ABSENT
    aliens = _aliens(screen)
    shields, shield_columns = _shields(screen)
    bullets = _alien_bullets(ram)
    fleet_x = int(ram[26])
    fleet_vx = _fleet_vx(fleet_x, previous, frames_elapsed)
    return {
        "ship_x": ship_x,
        "fleet_x": fleet_x,
        "fleet_vx": round(fleet_vx, 4),
        "aliens": aliens,
        "aliens_left": int(ram[17]),
        "alien_bullets": bullets,
        "player_shot_y": None if can_fire else 2 * int(ram[85]) + 4,
        "shields": shields,
        "lives": int(ram[73]),
        "features": _features(
            ship_x, bool(can_fire), aliens, bullets, shield_columns, fleet_vx
        ),
    }
