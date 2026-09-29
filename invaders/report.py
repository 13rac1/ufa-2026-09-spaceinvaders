"""Build the README tables and the latency chart from results.json."""

import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from invaders.results import load_results

# The organizers' reference scores for human-normalized score:
# (score - HUMAN_LOW) / (HUMAN_HIGH - HUMAN_LOW).
HUMAN_LOW = 148.0
HUMAN_HIGH = 1668.7

# Player row order for the summary table; a player not listed here (there is
# none today) would sort after these, alphabetically.
PLAYER_ORDER = [
    "code", "code-la", "jev-t3", "jev-t2", "jev-t1", "llm-t2", "llm-t1", "qwen-t2", "qwen-t1",
    "always-fire", "random",
]

# What each decider is told before it decides; see FAIR_EVALUATION.md.
TIER_NOTE = {
    1: "Tier 1: decoded positions",
    2: "Tier 2: exact facts, relative",
    3: "Tier 3: code verdicts (reference)",
}
MODE_ORDER = ["turn", "realtime"]


def human_normalized(score: float) -> float:
    """Normalize a raw score against the organizers' human low/high reference."""
    return (score - HUMAN_LOW) / (HUMAN_HIGH - HUMAN_LOW)


def every_record(results: dict) -> list[dict]:
    """Every run record, decider and baseline alike, all versions."""
    return list(results["runs"]) + list(results["baseline"]["runs"])


def all_records(results: dict) -> list[dict]:
    """The run records of each player's latest version (by the order runs were added).

    The tables and the chart describe the current players; earlier versions appear
    only in the version history.
    """
    records = every_record(results)
    latest: dict[str, str | None] = {}
    for r in sorted(records, key=lambda r: r.get("run", 0)):
        latest[r["player"]] = r.get("player_version")
    return [r for r in records if r.get("player_version") == latest[r["player"]]]


def build_version_history(results: dict) -> str:
    """Markdown table: mean score per player version, turn mode, runs without added delay."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in every_record(results):
        if r["mode"] == "turn" and not r.get("added_delay_ms"):
            groups.setdefault((r["player"], r.get("player_version") or "v1"), []).append(r)
    lines = [
        "| player | version | games | seeds | mean score | notes |",
        "|---|---|---|---|---|---|",
    ]
    for (player, version), runs in sorted(groups.items(), key=lambda kv: (_sort_key(kv[0][0], "turn"), kv[0][1])):
        seeds = sorted(r["seed"] for r in runs)
        notes = next((r["notes"] for r in runs if r.get("notes")), "")
        lines.append(
            f"| {player} | {version} | {len(runs)} | {seeds[0]}-{seeds[-1]} | "
            f"{statistics.mean(r['score'] for r in runs):.1f} | {notes} |"
        )
    return "\n".join(lines)


def _mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _stdev(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def _sort_key(player: str, mode: str) -> tuple:
    player_rank = PLAYER_ORDER.index(player) if player in PLAYER_ORDER else len(PLAYER_ORDER)
    mode_rank = MODE_ORDER.index(mode) if mode in MODE_ORDER else len(MODE_ORDER)
    return (player_rank, player, mode_rank, mode)


def group_by_player_mode(records: list[dict]) -> dict[tuple[str, str], list[dict]]:
    """Group records by (player, mode)."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for record in records:
        key = (record["player"], record["mode"])
        groups.setdefault(key, []).append(record)
    return groups


def scores_by_seed(records: list[dict], player: str, mode: str) -> dict[int, float]:
    """Mean score per seed for one (player, mode), across records that share a seed."""
    seed_scores: dict[int, list[float]] = {}
    for record in records:
        if record["player"] == player and record["mode"] == mode:
            seed_scores.setdefault(record["seed"], []).append(record["score"])
    return {seed: statistics.mean(scores) for seed, scores in seed_scores.items()}


def summarize_group(records: list[dict]) -> dict:
    """Compute one summary row's fields for a (player, mode) group of records."""
    scores = [r["score"] for r in records]
    steps = [r["steps"] for r in records]
    p50s = [r["latency_ms_p50"] for r in records]
    p95s = [r["latency_ms_p95"] for r in records]
    model_calls = [r["model_calls"] for r in records]
    input_tokens = [r["input_tokens"] for r in records]
    output_tokens = [r["output_tokens"] for r in records]
    costs = [r["cost_usd"] for r in records if r.get("cost_usd") is not None]
    total_decisions = sum(r["decisions"] for r in records)
    total_fallback = sum(r["fallback_actions"] for r in records)
    total_errors = sum(sum(r.get("errors_by_status", {}).values()) for r in records)
    served_models = sorted({r["served_model"] for r in records if r.get("served_model")})

    return {
        "games": len(records),
        "mean_score": _mean(scores),
        "median_score": _median(scores),
        "min_score": min(scores) if scores else None,
        "max_score": max(scores) if scores else None,
        "stdev_score": _stdev(scores),
        "human_norm_mean": _mean([human_normalized(s) for s in scores]),
        "mean_steps": _mean(steps),
        "latency_p50_ms": _median(p50s),
        "latency_p95_ms": _median(p95s),
        "model_calls_per_game": _mean(model_calls),
        "input_tokens_per_game": _mean(input_tokens),
        "output_tokens_per_game": _mean(output_tokens),
        "cost_per_game": _mean(costs) if costs else None,
        "fallback_rate": (total_fallback / total_decisions) if total_decisions else None,
        "error_count": total_errors,
        "served_models": ", ".join(served_models) if served_models else "n/a",
    }


def _fmt(value: float | None, decimals: int) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{decimals}f}"


def _no_added_delay(records: list[dict]) -> list[dict]:
    """Runs played without injected latency; the latency sweep has its own section."""
    return [r for r in records if not r.get("added_delay_ms")]


def build_summary_table(records: list[dict]) -> str:
    """Markdown summary table, one row per (player, mode), in PLAYER_ORDER then mode order.

    Runs with added delay are left out: they belong to the latency curve, and mixing
    them in would describe no configuration that was actually played.
    """
    groups = group_by_player_mode(_no_added_delay(records))
    keys = sorted(groups, key=lambda k: _sort_key(*k))

    columns = [
        "player",
        "mode",
        "games",
        "mean score",
        "median",
        "min",
        "max",
        "stdev",
        "human-norm mean",
        "mean steps",
        "latency p50 (ms)",
        "latency p95 (ms)",
        "model calls/game",
        "input tok/game",
        "output tok/game",
        "cost/game ($)",
        "fallback rate",
        "errors",
        "served model(s)",
    ]
    header = "| " + " | ".join(columns) + " |"
    sep = "|" + "---|" * len(columns)
    lines = [header, sep]

    for player, mode in keys:
        s = summarize_group(groups[(player, mode)])
        lines.append(
            "| "
            + " | ".join(
                [
                    player,
                    mode,
                    str(s["games"]),
                    _fmt(s["mean_score"], 1),
                    _fmt(s["median_score"], 1),
                    _fmt(s["min_score"], 1),
                    _fmt(s["max_score"], 1),
                    _fmt(s["stdev_score"], 1),
                    _fmt(s["human_norm_mean"], 3),
                    _fmt(s["mean_steps"], 1),
                    _fmt(s["latency_p50_ms"], 2),
                    _fmt(s["latency_p95_ms"], 2),
                    _fmt(s["model_calls_per_game"], 2),
                    _fmt(s["input_tokens_per_game"], 1),
                    _fmt(s["output_tokens_per_game"], 1),
                    _fmt(s["cost_per_game"], 4),
                    _fmt(s["fallback_rate"], 3),
                    str(s["error_count"]),
                    s["served_models"],
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def build_head_to_head(records: list[dict], jev: str = "jev-t2", llm: str = "llm-t2") -> str:
    """Markdown head-to-head table for a JEV and an LLM row in mode turn, per shared seed."""
    jev_scores = scores_by_seed(records, jev, "turn")
    llm_scores = scores_by_seed(records, llm, "turn")

    if not jev_scores:
        return f"No head-to-head: {jev} has no turn-mode runs."
    if not llm_scores:
        return f"No head-to-head: {llm} has no turn-mode runs."

    shared_seeds = sorted(set(jev_scores) & set(llm_scores))
    if not shared_seeds:
        return f"No head-to-head: {jev} and {llm} share no seeds in mode turn."

    lines = [
        f"| seed | {jev} score | {llm} score | winner |",
        "|---|---|---|---|",
    ]
    jev_wins = 0
    llm_wins = 0
    ties = 0
    for seed in shared_seeds:
        jev_score = jev_scores[seed]
        llm_score = llm_scores[seed]
        if jev_score > llm_score:
            winner = jev
            jev_wins += 1
        elif llm_score > jev_score:
            winner = llm
            llm_wins += 1
        else:
            winner = "tie"
            ties += 1
        lines.append(f"| {seed} | {jev_score:.1f} | {llm_score:.1f} | {winner} |")

    lines.append("")
    lines.append(
        f"Total: {jev} wins {jev_wins}, {llm} wins {llm_wins}, ties {ties} "
        f"(of {len(shared_seeds)} shared seeds)."
    )
    return "\n".join(lines)


def build_ladder(records: list[dict]) -> str:
    """Markdown table: each decider at its input tier, turn and realtime, speed and cost.

    Runs with added delay are left out; they belong to the latency curve.
    """
    rows = {}
    for r in records:
        if r.get("added_delay_ms"):
            continue
        rows.setdefault(r["player"], []).append(r)
    lines = [
        "| decider | input | turn mean (n) | realtime mean (n) | latency p50 (ms) | "
        "cost per game (USD) |",
        "|---|---|---|---|---|---|",
    ]
    for player in sorted(rows, key=lambda p: _sort_key(p, "turn")):
        runs = rows[player]
        tier = next((r.get("input_tier") for r in runs if r.get("input_tier")), None)
        cells = []
        for mode in ("turn", "realtime"):
            scores = [r["score"] for r in runs if r["mode"] == mode]
            cells.append(f"{statistics.mean(scores):.0f} ({len(scores)})" if scores else "-")
        latency = statistics.median(r["latency_ms_p50"] for r in runs)
        costs = [r["cost_usd"] for r in runs if r.get("cost_usd") is not None]
        cost = f"{statistics.mean(costs):.4f}" if costs else "n/a"
        note = TIER_NOTE.get(tier, "rules over the decoded state" if player.startswith("code")
                             else "none: presses FIRE every step" if player == "always-fire"
                             else "no input")
        lines.append(f"| {player} | {note} | {cells[0]} | {cells[1]} | {latency:.1f} | {cost} |")
    return "\n".join(lines)


def build_turn_vs_realtime(records: list[dict]) -> str:
    """Markdown table of mean turn vs. realtime (added_delay_ms 0) score, per player.

    Only seeds played in both modes count, so the two means compare the same games.
    """
    # The code players decide in under 0.01 ms, so their realtime and turn games are
    # the same game; comparing them says nothing.
    players = sorted(
        {r["player"] for r in records if not r["player"].startswith("code")},
        key=lambda p: PLAYER_ORDER.index(p) if p in PLAYER_ORDER else len(PLAYER_ORDER),
    )

    rows = []
    for player in players:
        turn = {
            r["seed"]: r["score"]
            for r in records
            if r["player"] == player and r["mode"] == "turn" and not r.get("added_delay_ms")
        }
        realtime = {
            r["seed"]: r["score"]
            for r in records
            if r["player"] == player and r["mode"] == "realtime" and not r.get("added_delay_ms")
        }
        seeds = sorted(set(turn) & set(realtime))
        if not seeds:
            continue
        turn_scores = [turn[s] for s in seeds]
        realtime_scores = [realtime[s] for s in seeds]
        turn_mean = statistics.mean(turn_scores)
        realtime_mean = statistics.mean(realtime_scores)
        drop_pct = ((turn_mean - realtime_mean) / turn_mean * 100) if turn_mean else None
        rows.append((player, len(seeds), turn_mean, realtime_mean, drop_pct))

    if not rows:
        return "No player has runs in both mode turn and mode realtime at added_delay_ms 0."

    lines = [
        "| player | shared seeds | mean turn score | mean realtime score | drop (%) |",
        "|---|---|---|---|---|",
    ]
    for player, n, turn_mean, realtime_mean, drop_pct in rows:
        lines.append(
            f"| {player} | {n} | {turn_mean:.1f} | {realtime_mean:.1f} | {_fmt(drop_pct, 1)} |"
        )
    return "\n".join(lines)


# The players whose realtime runs sweep added delays, with their chart labels.
CURVE_PLAYERS = {
    "code": "code, tuned for 0 ms",
    "code-la": "code, latency-aware",
}


def latency_curve_points(
    records: list[dict], player: str = "code"
) -> list[tuple[float, float, int]]:
    """(added_delay_ms, mean score, n) for a code player's realtime runs, sorted by delay."""
    by_delay: dict[float, list[float]] = {}
    for r in records:
        if r["player"] == player and r["mode"] == "realtime":
            by_delay.setdefault(r["added_delay_ms"], []).append(r["score"])
    return [
        (delay, statistics.mean(scores), len(scores)) for delay, scores in sorted(by_delay.items())
    ]


def build_latency_table(records: list[dict]) -> str:
    """Markdown table: added_delay_ms vs mean score (and n) of each code player."""
    curves = {p: dict((d, (m, n)) for d, m, n in latency_curve_points(records, p)) for p in CURVE_PLAYERS}
    curves = {p: c for p, c in curves.items() if c}
    if not curves:
        return "No code realtime runs to build a latency curve from."

    players = list(curves)
    lines = [
        "| added_delay_ms | " + " | ".join(f"{CURVE_PLAYERS[p]} (mean, n)" for p in players) + " |",
        "|---|" + "---|" * len(players),
    ]
    for delay in sorted({d for c in curves.values() for d in c}):
        cells = []
        for p in players:
            mean_n = curves[p].get(delay)
            cells.append(f"{mean_n[0]:.1f} ({mean_n[1]})" if mean_n else "n/a")
        lines.append(f"| {delay:g} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


REGENERATE_BLOCK = """```
python -m invaders bench --players code,code-la,random,jev,llm --seeds 101-110 \\
    --modes turn,realtime --delays 0,50,100,250,500,1000,2000 --skip-existing
python -m invaders report --out report/
```"""


def build_readme(results: dict) -> str:
    """Build the full README.md text from a loaded results.json."""
    records = all_records(results)

    return "\n\n".join(
        [
            "# Space Invaders benchmark report",
            "This file is generated by `python -m invaders report`. Do not edit it by "
            "hand; regenerate it instead (see \"How to regenerate\" below).",
            "## The input tier ladder\n\n" + build_ladder(records),
            "## Summary\n\n" + build_summary_table(records),
            "## Head-to-head at Tier 2: jev-t2 vs. llm-t2 (mode turn)\n\n"
            + build_head_to_head(records, "jev-t2", "llm-t2"),
            "## Head-to-head at Tier 1: jev-t1 vs. llm-t1 (mode turn)\n\n"
            + build_head_to_head(records, "jev-t1", "llm-t1"),
            "## Turn versus realtime\n\n" + build_turn_vs_realtime(records),
            "## Latency curve\n\n"
            + build_latency_table(records)
            + "\n\nSee `latency_curve.png` for the chart.\n\n"
            "![Latency curve](latency_curve.png)",
            "## Version history (turn mode)\n\nThe tables above use each player's "
            "latest version.\n\n" + build_version_history(results),
            "## How to regenerate\n\n" + REGENERATE_BLOCK,
        ]
    ) + "\n"


def plot_latency_curve(results: dict, out_path: Path) -> None:
    """Draw the latency curve: code's realtime score by added delay, other players marked."""
    records = all_records(results)
    curves = {p: latency_curve_points(records, p) for p in CURVE_PLAYERS}
    points = [pt for c in curves.values() for pt in c]

    fig, ax = plt.subplots(figsize=(8, 5), facecolor="white")
    ax.set_facecolor("white")

    positive_delays = [d for d, _, _ in points if d > 0]
    zero_x = min(positive_delays) / 10 if positive_delays else 1.0

    curve_styles = {"code": ("#1f77b4", "o", "-"), "code-la": ("#ff7f0e", "^", "-")}
    for player, curve in curves.items():
        if curve:
            color, marker, style = curve_styles[player]
            ax.plot(
                [zero_x if d == 0 else d for d, _, _ in curve],
                [score for _, score, _ in curve],
                marker=marker, linestyle=style, color=color,
                label=f"{CURVE_PLAYERS[player]} (realtime, by added delay)",
            )

    other_players = sorted(
        {r["player"] for r in records if r["player"] not in (*CURVE_PLAYERS, "random")}
    )
    marker_colors = ["#d62728", "#2ca02c", "#9467bd", "#8c564b", "#e377c2"]
    for i, player in enumerate(other_players):
        realtime = [
            r
            for r in records
            if r["player"] == player and r["mode"] == "realtime" and r["added_delay_ms"] == 0
        ]
        if not realtime:
            continue
        mean_score = statistics.mean(r["score"] for r in realtime)
        median_latency = statistics.median(r["latency_ms_p50"] for r in realtime)
        x = zero_x if median_latency <= 0 else median_latency
        ax.scatter(
            [x], [mean_score], marker="s", s=80, color=marker_colors[i % len(marker_colors)],
            label=f"{player} (at measured median latency)", zorder=5,
        )

    random_turn = [r["score"] for r in records if r["player"] == "random" and r["mode"] == "turn"]
    if random_turn:
        ax.axhline(
            statistics.mean(random_turn), color="gray", linestyle="--", linewidth=1,
            label="random mean (turn)",
        )
    ax.axhline(
        HUMAN_HIGH, color="black", linestyle="--", linewidth=1, label="human reference"
    )

    ax.set_xscale("log")
    tick_positions = [zero_x] + sorted(set(d for d, _, _ in points if d > 0))  # all curves
    tick_labels = ["0"] + [f"{d:g}" for d in sorted(set(d for d, _, _ in points if d > 0))]
    if tick_positions:
        ax.set_xticks(tick_positions)
        ax.set_xticklabels(tick_labels)
        ax.minorticks_off()

    ax.set_xlabel("Decision latency (ms, log scale)")
    ax.set_ylabel("Mean score")
    ax.set_title("Score versus decision latency")
    ax.legend(loc="best", fontsize="small")
    fig.tight_layout()
    fig.savefig(out_path, facecolor="white")
    plt.close(fig)


def generate_report(results_path: Path, out_dir: Path) -> None:
    """Read results_path and write README.md and latency_curve.png into out_dir."""
    results = load_results(Path(results_path))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    readme_text = build_readme(results)
    (out_dir / "README.md").write_text(readme_text)

    plot_latency_curve(results, out_dir / "latency_curve.png")
