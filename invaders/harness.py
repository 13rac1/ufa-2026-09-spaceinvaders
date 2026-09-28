"""Run one game and produce its run record."""

import json
import os
import time

import imageio
import numpy as np

from invaders.env import make_env
from invaders.state import decode

NOOP = 0
FRAMES_PER_STEP = 4
FPS = 60
VIDEO_FPS = FPS // FRAMES_PER_STEP  # one frame per env.step


def hold_steps(latency_ms: float, carried_frames: float = 0.0) -> tuple[int, float]:
    """Return the env steps to hold the previous action in realtime mode.

    At 60 frames per second, latency_ms spans latency_ms / 1000 * 60 frames. Each
    env step is 4 frames. Whole steps are held now; the remaining fraction of a step
    is carried to the next decision, so a fast player loses only the time it takes.
    Returns (steps to hold, frames carried to the next decision).
    """
    frames = carried_frames + latency_ms / 1000 * FPS
    k = int(frames // FRAMES_PER_STEP)
    return k, frames - k * FRAMES_PER_STEP


def run_game(
    player,
    seed: int,
    mode: str,
    added_delay_ms: float = 0,
    max_steps: int | None = None,
    record_video: str | None = None,
    log_path: str | None = None,
) -> dict:
    """Play one game with player and return its run record.

    mode "turn" applies one decision per env.step. mode "realtime" does not
    wait for the decision: before applying it, the env is stepped holding the
    previous action for the whole steps that latency_ms spans (60 fps, 4
    frames per env step; see hold_steps), stopping early if the game ends or
    max_steps is reached. Hold steps count toward steps and max_steps but are not
    decisions.

    added_delay_ms is added to every measured decision latency
    arithmetically; the harness never sleeps, in either mode.
    """
    if mode not in ("turn", "realtime"):
        raise ValueError(f"unknown mode: {mode!r}")

    env = make_env()
    start = time.perf_counter()

    if record_video is not None:
        os.makedirs(os.path.dirname(record_video) or ".", exist_ok=True)
    if log_path is not None:
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)

    video_writer = (
        imageio.get_writer(record_video, fps=VIDEO_FPS, macro_block_size=1)
        if record_video is not None
        else None
    )
    log_file = open(log_path, "w") if log_path is not None else None

    obs, info = env.reset(seed=seed)
    player.reset(seed)

    previous_action = NOOP
    carried_frames = 0.0
    previous_state = None
    previous_frame = 0
    score = 0.0
    steps = 0
    decisions = 0
    latencies: list[float] = []
    confidences: list[float] = []
    model_calls = 0
    input_tokens = 0
    output_tokens = 0
    errors_by_status: dict[str, int] = {}
    retries = 0
    fallback_actions = 0
    served_model = None
    terminated = False
    truncated = False

    def steps_left() -> bool:
        if terminated or truncated:
            return False
        return max_steps is None or steps < max_steps

    def take_step(action: int) -> None:
        nonlocal obs, info, score, steps, terminated, truncated
        obs, reward, terminated, truncated, info = env.step(action)
        score += reward
        steps += 1
        if video_writer is not None:
            video_writer.append_data(env.unwrapped.ale.getScreenRGB())

    try:
        while steps_left():
            ram = obs
            screen = env.unwrapped.ale.getScreenRGB()
            frame = info.get("episode_frame_number", 0)
            state = decode(ram, screen, previous_state, frame - previous_frame)
            previous_state, previous_frame = state, frame

            t0 = time.perf_counter()
            decision = player.decide(state, previous_action)
            t1 = time.perf_counter()
            latency_ms = (t1 - t0) * 1000.0 + added_delay_ms

            decisions += 1
            latencies.append(latency_ms)
            model_calls += decision.model_calls
            input_tokens += decision.input_tokens
            output_tokens += decision.output_tokens
            if decision.confidence is not None:
                confidences.append(decision.confidence)
            if decision.error_status is not None:
                key = str(decision.error_status)
                errors_by_status[key] = errors_by_status.get(key, 0) + 1
            retries += decision.retries
            if decision.fallback:
                fallback_actions += 1
            if decision.served_model is not None:
                served_model = decision.served_model

            if log_file is not None:
                log_file.write(
                    json.dumps(
                        {
                            "step": steps,
                            "state": state,
                            "action": decision.action,
                            "confidence": decision.confidence,
                            "latency_ms": latency_ms,
                            "error_status": decision.error_status,
                        }
                    )
                    + "\n"
                )

            if mode == "turn":
                take_step(decision.action)
            else:
                k, carried_frames = hold_steps(latency_ms, carried_frames)
                for _ in range(k):
                    if not steps_left():
                        break
                    take_step(previous_action)
                if steps_left():
                    take_step(decision.action)

            previous_action = decision.action
    finally:
        if video_writer is not None:
            video_writer.close()
        if log_file is not None:
            log_file.close()
        env.close()

    wall_clock_s = time.perf_counter() - start
    lives = info.get("lives", 3)

    record = {
        "seed": seed,
        "score": float(score),
        "steps": steps,
        "frames": info.get("episode_frame_number", steps * FRAMES_PER_STEP),
        "lives_lost": 3 - lives,
        "terminated": bool(terminated),
        "truncated": bool(truncated),
        "model_calls": model_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms_p50": float(np.percentile(latencies, 50)) if latencies else 0.0,
        "latency_ms_p95": float(np.percentile(latencies, 95)) if latencies else 0.0,
        "latency_ms_total": float(sum(latencies)),
        "errors_by_status": errors_by_status,
        "retries": retries,
        "fallback_actions": fallback_actions,
        "wall_clock_s": wall_clock_s,
        "served_model": served_model,
        "player": player.name,
        "mode": mode,
        "added_delay_ms": added_delay_ms,
        "decisions": decisions,
        "max_steps": max_steps,
    }
    if confidences:
        record["mean_confidence"] = float(np.mean(confidences))
        record["low_conf_rate"] = float(np.mean([c < 0.6 for c in confidences]))

    return record
