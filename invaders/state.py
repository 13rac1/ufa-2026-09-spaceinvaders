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
- player shot: top y = 2 * RAM[85] + 4; RAM[85] == 246 when no shot is in flight;
  121 or 123 while a shot is stopped by a shield (a state code, not a position). The
  shot leaves one pixel right of the ship's center.
- RAM[17]: aliens left. RAM[73]: lives. RAM[26]: fleet x. The fleet moves in jumps of
  `step` pixels every `period` frames (see FLEET_MOTION) and turns when its outermost
  alien reaches screen x 27 or 130 (RAM[26] 23 and 50 for the full fleet). No RAM byte
  holds the direction or the move timer; both are inferred from the observed motion in
  the previous decoded state.
- ship rows y 185 to 194; shields y 157 to 174; aliens 8 by 10 pixels.
- mothership: drawn every frame at y 12 to 19, 7 pixels wide, colour (151, 25, 122);
  moves 0.25 pixels per frame without turning; 200 points. Read from the screen.
"""

import numpy as np

# Action indices of ALE/SpaceInvaders-v5 with the minimal action set.
ACTIONS = ("NOOP", "FIRE", "RIGHT", "LEFT", "RIGHTFIRE", "LEFTFIRE")

ABSENT = 246
SHOT_BLOCKED = (121, 123)  # RAM[85] codes for a shot stopped by a shield, not positions
SHIP_MIN_X, SHIP_MAX_X = 37, 119
SHIP_TOP_Y = 185
SHIP_BOTTOM_Y = 194
SHIP_HALF_WIDTH = 3  # the ship is 7 pixels wide
SHIP_SPEED = 0.5  # pixels per frame
SHOT_OFFSET = 1  # the shot's x is the ship's center plus this
SHOT_SPEED = 2.0  # pixels per frame, upward
FLEET_MIN_X, FLEET_MAX_X = 23, 50  # RAM[26] where the full-width fleet turns
# The fleet turns when its outermost alien reaches these screen columns (measured on
# tuning seeds), so a fleet without its outer columns travels further.
LEFT_TURN_ALIEN_X, RIGHT_TURN_ALIEN_X = 27, 130
PHASE_LEAD_BELOW = 5  # at this many aliens left or fewer, aim with the fleet's discrete moves
# Measured frame by frame on tuning seeds: (aliens left at least, frames per move,
# pixels per move).
FLEET_MOTION = (
    (23, 32, 1), (22, 64, 1), (8, 22, 2), (5, 16, 3), (4, 11, 3), (3, 7, 3), (2, 7, 4),
    (1, 4, 5),
)
SHIELD_TOP_Y, SHIELD_BOTTOM_Y = 157, 174
BULLET_HEIGHT = 8
BULLET_SPEED = 1.0  # pixels per frame
FRAMES_PER_STEP = 4
HIT_MARGIN = 1  # extra pixels on each side of the ship when testing for a hit
ALIGNED_PX = 4  # fire only when the target's center is this close to the ship's
HORIZON_FRAMES = 40  # bullets further away than this are not a threat yet

ALIEN_COLOR = (134, 134, 29)
SHIELD_COLOR = (181, 83, 40)
MOTHERSHIP_COLOR = (151, 25, 122)
SHOT_COLOR = (142, 142, 142)  # the player's shot; drawn on the frames the harness observes
MOTHERSHIP_Y = 16  # center row
MOTHERSHIP_SPEED = 0.25  # pixels per frame
MOTHERSHIP_SAFE_ROW_Y = 155
INVASION_Y = 160  # the lowest alien row's center y at which the game ends (measured 163-165)
DESCENT_PX = 10  # the fleet drops this far each time it turns at an edge
URGENT_FRAMES = 1e9  # below this margin to invasion only the lowest row counts
MOTHERSHIP_MIN_MARGIN = 0.0  # frames to invasion needed before chasing the mothership
POINTS_WEIGHT = 1.0  # how much a higher row's points count against its extra frames  # chase the mothership only while the lowest aliens are above this


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


def _mothership(screen: np.ndarray, previous: dict | None, frames_elapsed: int) -> dict | None:
    """The mothership's center x and velocity, or None when it is not on the screen."""
    mask = (screen[12:20] == MOTHERSHIP_COLOR).all(-1)
    xs = np.where(mask.any(0))[0]
    if len(xs) == 0 or xs[-1] - xs[0] > 12:  # absent, or its first frame (full width)
        return None
    x = (int(xs[0]) + int(xs[-1])) / 2
    vx = 0.0
    old = previous.get("mothership") if previous else None
    if old is not None and frames_elapsed > 0:
        dx = x - old["x"]
        vx = MOTHERSHIP_SPEED * (1 if dx > 0 else -1) if dx else old["vx"]
    return {"x": x, "vx": vx}


def _shot_x(screen: np.ndarray) -> int | None:
    """Column of the player's shot on the screen, or None when it is not drawn."""
    mask = (screen[20:SHIP_TOP_Y] == SHOT_COLOR).all(-1)
    columns = np.where(mask.any(0))[0]
    return int(columns[0]) if len(columns) == 1 else None


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


def _lead_x(alien: dict, fleet: dict) -> float:
    """Where the alien will be when a shot fired now reaches its row."""
    return alien["x"] + _fleet_shift(fleet["x"], fleet, (SHIP_TOP_Y - alien["y"]) / SHOT_SPEED)


def _frames_to_invasion(lowest_y: float, fleet: dict) -> float:
    """Frames until the lowest alien row reaches INVASION_Y, from the fleet's motion.

    The fleet drops DESCENT_PX each time it turns at an edge; the estimate assumes its
    current speed (it speeds up as aliens die, so the real margin is shorter).
    """
    descents = int(np.ceil((INVASION_Y - lowest_y) / DESCENT_PX))
    if descents <= 0:
        return 0.0
    speed = fleet["step"] / fleet["period"]
    lo, hi = fleet.get("min_x", FLEET_MIN_X), fleet.get("max_x", FLEET_MAX_X)
    x = fleet.get("x", lo)
    to_edge = (hi - x if fleet["dir"] > 0 else x - lo) / speed
    return to_edge + (descents - 1) * (hi - lo) / speed


def _shot_victim(aliens, fleet, shot) -> dict | None:
    """The alien the player's shot in flight will hit first, or None."""
    if not shot or shot.get("x") is None or shot.get("y") is None:
        return None
    hits = []
    for a in aliens:
        frames = (shot["y"] - a["y"]) / SHOT_SPEED
        if frames >= 0 and abs(a["x"] + _fleet_shift(fleet["x"], fleet, frames) - shot["x"]) <= 4:
            hits.append(a)
    return max(hits, key=lambda a: a["y"]) if hits else None


def _choose_target(aliens, fleet, shot_x, shield_columns) -> tuple[int | None, bool, float]:
    """Return (target_dx, target_behind_shield, frames_to_invasion).

    Invasion control: while the fleet is far from landing, aim at the clear alien that
    gives the most points per frame (travel plus shot flight; rows are worth 5 to 30
    points from the bottom up). When fewer than URGENT_FRAMES remain, only the lowest
    row counts, because removing it buys time. With no clear alien in the lowest row,
    aim through a shield.
    """
    if not aliens:
        return None, False, float("inf")

    def reachable(a):
        return SHIP_MIN_X <= a["x"] - SHOT_OFFSET <= SHIP_MAX_X and not shield_columns[a["x"]]

    def travel(a):
        return abs(_lead_x(a, fleet) - shot_x)

    lowest_y = max(a["y"] for a in aliens)
    margin = _frames_to_invasion(lowest_y, fleet)
    bottom_row = [a for a in aliens if a["y"] >= lowest_y - 2]
    clear_bottom = [a for a in bottom_row if reachable(a)]
    if fleet.get("outer_first"):
        # A fleet without its outer columns travels further before each descent.
        left, right = min(a["x"] for a in aliens), max(a["x"] for a in aliens)
        columns = {}
        for a in aliens:
            if (a["x"] <= left + 4 or a["x"] >= right - 4) and reachable(a):
                key = round(a["x"] / 8)
                if key not in columns or a["y"] > columns[key]["y"]:
                    columns[key] = a
        pool = list(columns.values()) or clear_bottom
    elif margin < URGENT_FRAMES or not clear_bottom:
        pool = clear_bottom
    else:
        rows = sorted({round(a["y"] / 6) for a in aliens}, reverse=True)  # bottom first
        def value(a):
            points = 5 * (rows.index(round(a["y"] / 6)) + 1)
            frames = travel(a) / SHIP_SPEED + (SHIP_TOP_Y - a["y"]) / SHOT_SPEED
            return points ** POINTS_WEIGHT / max(frames, 1.0)
        clear = [a for a in aliens if reachable(a)]
        pool = [max(clear, key=value)] if clear else []
    target = min(pool or bottom_row, key=travel)
    return round(_lead_x(target, fleet) - shot_x), not pool, margin


def _features(
    ship_x, can_fire, aliens, bullets, shield_columns, fleet, mothership, shot=None
) -> dict:
    shot_x = ship_x + SHOT_OFFSET
    threats = [b for b in bullets if not _blocked(b, shield_columns)]
    safe = {
        name: not any(_hits(b, ship_x, d) for b in threats)
        for name, d in (("left", -1), ("stay", 0), ("right", 1))
    }
    # While a shot flies, aim at the next target: the shot's victim is as good as gone.
    victim = _shot_victim(aliens, fleet, shot)
    target_dx, target_behind_shield, margin = _choose_target(
        [a for a in aliens if a is not victim] or aliens, fleet, shot_x, shield_columns
    )
    # The mothership is worth 200 points against 5 to 30 for an alien: chase it while
    # the fleet is high enough, if the intercept point is on the ship's range.
    target_kind = "alien" if aliens else None
    if mothership is not None and mothership["vx"] and (
        not aliens
        or (max(a["y"] for a in aliens) <= MOTHERSHIP_SAFE_ROW_Y and margin >= MOTHERSHIP_MIN_MARGIN)
    ):
        lead = mothership["x"] + mothership["vx"] * (SHIP_TOP_Y - MOTHERSHIP_Y) / SHOT_SPEED
        if SHIP_MIN_X <= lead - SHOT_OFFSET <= SHIP_MAX_X and not shield_columns[int(lead)]:
            target_dx = round(lead - shot_x)
            target_kind = "mothership"
            target_behind_shield = False
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
        "target_kind": target_kind,
        "aligned": target_dx is not None and abs(target_dx) <= ALIGNED_PX,
        "under_shield": bool(shield_columns[shot_x]),
        "target_behind_shield": target_behind_shield,
        "nearest_threat": nearest_threat,
    }


def _table_motion(aliens_left: int) -> tuple[int, int]:
    for at_least, period, step in FLEET_MOTION:
        if aliens_left >= at_least:
            return period, step
    return FLEET_MOTION[-1][1], FLEET_MOTION[-1][2]


def _fleet_motion(
    fleet_x: int, aliens_left: int, previous: dict | None, frames_elapsed: int
) -> dict:
    """Infer the fleet's direction and move phase from its observed motion.

    The move period and size come from FLEET_MOTION, measured frame by frame: at the
    harness's 4-frame sampling an observed interval cannot tell 7 frames from 4 or 8.
    The direction is that of the last observed move; the phase is the frames since it.
    """
    period, step = _table_motion(aliens_left)
    fleet = {"dir": 1, "step": step, "period": period, "since_move": 0, "left": aliens_left}
    old = previous.get("fleet") if previous else None
    if old is None or frames_elapsed <= 0:
        return fleet
    dx = fleet_x - previous["fleet_x"]
    if abs(dx) > 16:  # a new wave or a reset, not movement
        return fleet
    fleet["dir"] = (1 if dx > 0 else -1) if dx else old["dir"]
    fleet["since_move"] = 0 if dx else old["since_move"] + frames_elapsed
    return fleet


def _fleet_shift(fleet_x: int, fleet: dict, frames: float) -> float:
    """How far the fleet moves in the given frames, turning at its edges.

    Continuous at the fleet's average speed, so the aim point does not jump from one
    alien to the next as the move phase changes.
    """
    lo, hi = fleet.get("min_x", FLEET_MIN_X), fleet.get("max_x", FLEET_MAX_X)
    if fleet.get("left", 99) <= fleet.get("phase_below", 0):
        moves = int((fleet.get("since_move", 0) + frames) // fleet["period"])
        x, direction = fleet_x, fleet["dir"]
        for _ in range(moves):
            if not lo <= x + direction * fleet["step"] <= hi:
                direction = -direction  # the fleet drops and turns instead of moving
                continue
            x += direction * fleet["step"]
        return x - fleet_x
    speed = fleet["step"] / fleet["period"]
    x, direction, left = float(fleet_x), fleet["dir"], frames
    while left > 0:
        edge = hi if direction > 0 else lo
        to_edge = abs(edge - x) / speed
        if to_edge >= left:
            return x + direction * speed * left - fleet_x
        x, direction, left = edge, -direction, left - to_edge
    return x - fleet_x


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
    fleet = _fleet_motion(fleet_x, int(ram[17]), previous, frames_elapsed)
    fleet["x"] = fleet_x
    fleet.update(outer_first=True, phase_below=PHASE_LEAD_BELOW)
    if aliens:
        fleet["min_x"] = min(fleet_x, fleet_x - (min(a["x"] for a in aliens) - LEFT_TURN_ALIEN_X))
        fleet["max_x"] = max(fleet_x, fleet_x + (RIGHT_TURN_ALIEN_X - max(a["x"] for a in aliens)))
    mothership = _mothership(screen, previous, frames_elapsed)
    shot_y = None if can_fire or ram[85] in SHOT_BLOCKED else 2 * int(ram[85]) + 4
    shot = {"x": _shot_x(screen) if shot_y is not None else None, "y": shot_y}
    return {
        "ship_x": ship_x,
        "fleet_x": fleet_x,
        "fleet_vx": round(fleet["dir"] * fleet["step"] / fleet["period"], 4),
        "fleet": fleet,
        "aliens": aliens,
        "aliens_left": int(ram[17]),
        "alien_bullets": bullets,
        "player_shot_y": shot["y"],
        "player_shot_x": shot["x"],
        "player_shot_blocked": bool(ram[85] in SHOT_BLOCKED),
        "shields": shields,
        "mothership": mothership,
        "lives": int(ram[73]),
        "features": _features(
            ship_x, bool(can_fire), aliens, bullets, shield_columns, fleet, mothership,
            shot,
        ),
    }


def _move_direction(action: int) -> int:
    name = ACTIONS[action]
    return 1 if name.startswith("RIGHT") else -1 if name.startswith("LEFT") else 0


def project_features(state: dict, frames: float, held_action: int) -> dict:
    """Return the features of the state as it will be after the given frames.

    For a decider that knows its own latency: alien bullets fall, the fleet moves at
    its estimated velocity, and the ship moves with the action it holds meanwhile.
    Whether the ship can fire is left as observed.
    """
    ship_x = state["ship_x"] + _move_direction(held_action) * SHIP_SPEED * frames
    ship_x = int(round(min(max(ship_x, SHIP_MIN_X), SHIP_MAX_X)))
    bullets = [
        {"x": b["x"], "y": int(b["y"] + BULLET_SPEED * frames)}
        for b in state["alien_bullets"]
        if b["y"] + BULLET_SPEED * frames <= SHIP_BOTTOM_Y
    ]
    shift = state["fleet_vx"] * frames
    aliens = [{"x": int(round(a["x"] + shift)), "y": a["y"]} for a in state["aliens"]]
    aliens = [a for a in aliens if 0 <= a["x"] < 160]
    shield_columns = np.zeros(160, dtype=bool)
    for shield in state["shields"]:
        shield_columns[shield["x0"] : shield["x1"] + 1] = True
    return _features(
        ship_x,
        state["features"]["can_fire"],
        aliens,
        bullets,
        shield_columns,
        {**state["fleet"], "x": state["fleet_x"] + shift},
        state["mothership"],
        {"x": state["player_shot_x"], "y": state["player_shot_y"]},
    )



def _shield_columns(shields: list[dict]) -> np.ndarray:
    columns = np.zeros(160, dtype=bool)
    for shield in shields:
        columns[shield["x0"] : shield["x1"] + 1] = True
    return columns


def tier1_view(state: dict) -> dict:
    """Tier 1: the decoded objects as absolute screen positions, no arithmetic done.

    This is the organizers' recommended state (ship x, alien grid, alien bullets with
    position and velocity, shields, lives). It holds all the information the code
    player uses; the game's constants are stated in the question.
    """
    rows: dict[int, list[int]] = {}
    for alien in state["aliens"]:
        rows.setdefault(alien["y"], []).append(alien["x"])
    shot = None
    if state["player_shot_y"] is not None:
        shot = {"x": state["player_shot_x"], "y": state["player_shot_y"]}
    return {
        "ship": {"x": state["ship_x"], "lives": state["lives"]},
        "gun_ready": state["features"]["can_fire"],
        "player_shot": shot,
        "alien_bullets": [
            {"x": b["x"], "y": b["y"], "vy": BULLET_SPEED} for b in state["alien_bullets"]
        ],
        "alien_rows": [{"y": y, "x": sorted(xs)} for y, xs in sorted(rows.items())],
        "fleet_vx": state["fleet_vx"],
        "shields": [{"x0": s["x0"], "x1": s["x1"]} for s in state["shields"]],
        "mothership": state["mothership"],
    }


def _lane(dx: float, half_width: int) -> str:
    """A named position bucket: within the ship's width, or to one side of it."""
    return "over_ship" if abs(dx) <= half_width else ("left" if dx < 0 else "right")


def _arrival(frames: float) -> str:
    return "now" if frames <= 8 else ("soon" if frames <= 30 else "far")


def tier2_view(state: dict) -> dict:
    """Tier 2: the Tier 1 facts with the arithmetic done exactly, relative to the ship.

    Offsets are pixels, negative to the left. Bullets are measured from the ship's
    center; aliens and the mothership from the shot's column, at the moment a shot
    fired now would reach them. No verdicts: the view lists the candidate targets and
    leaves the choice, and whether to dodge, to the decider.
    """
    ship_x = state["ship_x"]
    shot_x = ship_x + SHOT_OFFSET
    columns = _shield_columns(state["shields"])
    fleet = state["fleet"]
    aliens = state["aliens"]
    lowest_y = max((a["y"] for a in aliens), default=None)
    bottom = [a for a in aliens if lowest_y is not None and a["y"] >= lowest_y - 2]
    mothership = None
    if state["mothership"] is not None and state["mothership"]["vx"]:
        m = state["mothership"]
        lead = m["x"] + m["vx"] * (SHIP_TOP_Y - MOTHERSHIP_Y) / SHOT_SPEED
        mothership = {
            "side": _lane(lead - shot_x, ALIGNED_PX),
            "dx_at_shot_arrival": round(lead - shot_x),
        }
    return {
        "lives": state["lives"],
        "gun_ready": state["features"]["can_fire"],
        "shield_above_ship": bool(columns[shot_x]),
        "room_to_move_px": {"left": ship_x - SHIP_MIN_X, "right": SHIP_MAX_X - ship_x},
        "alien_bullets": [
            {
                "lane": _lane(b["x"] - ship_x, SHIP_HALF_WIDTH + HIT_MARGIN),
                "arrival": _arrival(_frames_to_ship(b)),
                "dx": b["x"] - ship_x,
                "frames_to_ship_row": round(_frames_to_ship(b)),
                "stopped_by_shield": _blocked(b, columns),
            }
            for b in state["alien_bullets"]
        ],
        "lowest_row_aliens": sorted(
            (
                {
                    "side": _lane(_lead_x(a, fleet) - shot_x, ALIGNED_PX),
                    "dx_at_shot_arrival": round(_lead_x(a, fleet) - shot_x),
                    "behind_shield": bool(columns[min(max(a["x"], 0), 159)]),
                }
                for a in bottom
            ),
            key=lambda a: a["dx_at_shot_arrival"],
        ),
        "other_aliens": len(aliens) - len(bottom),
        "mothership": mothership,
    }


def tier2_compact_view(state: dict) -> dict:
    """Tier 2 v6: the Tier 2 facts, filtered and grouped for a literal reader.

    The same exact facts as tier2_view, less what cannot matter: bullets that a shield
    will stop are left out, and the aliens of the lowest row are grouped by side, as
    offsets at the moment a shot fired now would reach them. Aliens behind a shield
    are listed apart, because a shot cannot reach them. No verdicts.
    """
    view = tier2_view(state)
    aliens = {"left": [], "over_ship": [], "right": []}
    shielded = []
    for alien in view["lowest_row_aliens"]:
        if alien["behind_shield"]:
            shielded.append(alien["dx_at_shot_arrival"])
        else:
            aliens[alien["side"]].append(alien["dx_at_shot_arrival"])
    mothership = view["mothership"]
    return {
        "gun_ready": view["gun_ready"],
        "room_to_move_px": view["room_to_move_px"],
        "bullets": [
            {k: b[k] for k in ("lane", "arrival", "dx", "frames_to_ship_row")}
            for b in view["alien_bullets"]
            if not b["stopped_by_shield"]
        ],
        "aliens": aliens,
        "aliens_behind_shields": shielded,
        "mothership": (
            {"side": mothership["side"], "dx": mothership["dx_at_shot_arrival"]}
            if mothership else None
        ),
    }
