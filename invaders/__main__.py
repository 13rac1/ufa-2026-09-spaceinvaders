"""Command-line interface: play games, run the evaluation matrix, build the report."""

import argparse
import functools
import os
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from invaders.bench import build_matrix, existing_keys, game_key, play_and_record
from invaders.players.code_player import CodePlayer, LatencyAwareCodePlayer
from invaders.players.fire_player import AlwaysFirePlayer
from invaders.players.llm_player import LLMPlayer
from invaders.players.random_player import RandomPlayer
from invaders.players.systemone import MissingAPIKeyError, SystemOnePlayer
from invaders.report import generate_report
from invaders.results import RESULTS_FILENAME, load_results

# Each entry is a zero-argument factory; add one here to support a new player,
# the CLI needs no other change.
PLAYERS = {
    "code": CodePlayer,
    "code-la": LatencyAwareCodePlayer,
    "random": RandomPlayer,
    "always-fire": AlwaysFirePlayer,
    "jev-t1": functools.partial(
        SystemOnePlayer,
        name="jev-t1",
        base_url="https://api.typesafe.ai",
        model="jev-latest",
        api_key_env="TYPESAFE_API_KEY",
        provider="typesafe",
        tier=1,
    ),
    "jev-t2": functools.partial(
        SystemOnePlayer,
        name="jev-t2",
        base_url="https://api.typesafe.ai",
        model="jev-latest",
        api_key_env="TYPESAFE_API_KEY",
        provider="typesafe",
        tier=2,
    ),
    "jev-t3": functools.partial(
        SystemOnePlayer,
        name="jev-t3",
        base_url="https://api.typesafe.ai",
        model="jev-latest",
        api_key_env="TYPESAFE_API_KEY",
        provider="typesafe",
        tier=3,
    ),
    "llm-t1": functools.partial(LLMPlayer, name="llm-t1", tier=1),
    # Qwen on a local OpenAI-compatible server (LLM_BASE_URL, LLM_PROVIDER=openai, LLM_MODEL,
    # LLM_REASONING_EFFORT=none): an extra LLM row, free to run.
    "qwen-t1": functools.partial(LLMPlayer, name="qwen-t1", tier=1),
    "qwen-t2": functools.partial(LLMPlayer, name="qwen-t2", tier=2),
    "llm-t2": functools.partial(LLMPlayer, name="llm-t2", tier=2),
}

# The sdk_package/sdk_version recorded in a run's model entry, per player.
SDK_PACKAGES = {
    **{f"jev-t{t}": "httpx" for t in (1, 2, 3)},
    **{f"llm-t{t}": "system-one-adapter" for t in (1, 2)},
    **{f"qwen-t{t}": "system-one-adapter" for t in (1, 2)},
}

DEFAULT_BENCH_PLAYERS = "code,random"
DEFAULT_GAME_COST_USD = 0.30  # the cost assumed for a player's first game under --max-cost-usd
DEFAULT_BENCH_SEEDS = "101-110"
DEFAULT_BENCH_MODES = "turn,realtime"
DEFAULT_BENCH_DELAYS = "0,50,100,250,500,1000,2000"


def _package_version(package: str) -> str | None:
    try:
        return version(package)
    except PackageNotFoundError:
        return None


REPO_DIR = Path(__file__).resolve().parent.parent


def parse_seeds(spec: str) -> list[int]:
    """Parse a seed spec such as "1-5" or "1,3,7" into a list of seeds."""
    seeds: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            seeds.extend(range(int(lo), int(hi) + 1))
        else:
            seeds.append(int(part))
    return seeds


def parse_list(spec: str) -> list[str]:
    """Parse a comma-separated list, trimming whitespace and dropping empty parts."""
    return [part.strip() for part in spec.split(",") if part.strip()]


def parse_delays(spec: str) -> list[float]:
    """Parse a comma-separated list of delays in milliseconds."""
    return [float(part.strip()) for part in spec.split(",") if part.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="invaders")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="play games and record results")
    run.add_argument("--player", required=True, choices=sorted(PLAYERS))
    run.add_argument("--seeds", required=True, help='seed spec, e.g. "1-5" or "1,3,7"')
    run.add_argument("--mode", required=True, choices=["turn", "realtime"])
    run.add_argument("--delay-ms", type=float, default=0.0)
    run.add_argument("--max-steps", type=int, default=None)
    run.add_argument("--video-dir", default=None)
    run.add_argument("--log-dir", default=None)
    run.add_argument("--no-push", action="store_true")
    run.add_argument("--notes", default=None, help="one line on what changed and why")
    run.add_argument("--no-commit", action="store_true")

    bench = sub.add_parser("bench", help="run the whole evaluation matrix")
    bench.add_argument("--players", default=DEFAULT_BENCH_PLAYERS, help="comma-separated list")
    bench.add_argument(
        "--seeds", default=DEFAULT_BENCH_SEEDS, help='seed spec, e.g. "101-110" or "1,3,7"'
    )
    bench.add_argument("--modes", default=DEFAULT_BENCH_MODES, help="comma-separated list")
    bench.add_argument(
        "--delays",
        default=DEFAULT_BENCH_DELAYS,
        help="comma-separated added_delay_ms values; applies only to player code in realtime mode",
    )
    bench.add_argument("--max-steps", type=int, default=None)
    bench.add_argument("--no-commit", action="store_true")
    bench.add_argument("--no-push", action="store_true")
    bench.add_argument("--notes", default=None, help="one line on what changed and why")
    bench.add_argument(
        "--max-cost-usd", type=float, default=None,
        help="stop before a game that could take the spend of this bench past this cap",
    )
    bench.add_argument(
        "--skip-existing",
        action="store_true",
        help="skip a (player, mode, seed, added_delay_ms, max_steps) combination already "
        "in results.json, so an interrupted bench can resume",
    )

    ver = sub.add_parser("verify", help="replay recorded code and random games; match scores")
    ver.add_argument("--limit", type=int, default=None, help="check at most this many runs")

    diag = sub.add_parser("diagnose", help="diagnose a player on tuning seeds (not recorded)")
    diag.add_argument("--player", required=True, choices=sorted(PLAYERS))
    diag.add_argument("--seeds", default="1-40")
    diag.add_argument("--per-game", action="store_true")

    report = sub.add_parser("report", help="rebuild the tables and chart from results.json")
    report.add_argument("--results", default=None, help="path to results.json (default repo root)")
    report.add_argument("--out", default=None, help="output directory (default report/)")

    return parser


def run_command(args: argparse.Namespace) -> int:
    seeds = parse_seeds(args.seeds)
    player_factory = PLAYERS[args.player]

    try:
        player = player_factory()
    except MissingAPIKeyError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    sdk_package = SDK_PACKAGES.get(args.player)
    sdk_version = _package_version(sdk_package) if sdk_package else None

    for seed in seeds:
        video_path = None
        if args.video_dir is not None:
            video_dir = Path(args.video_dir)
            video_dir.mkdir(parents=True, exist_ok=True)
            video_path = str(video_dir / f"{args.player}-{args.mode}-seed{seed}.mp4")

        log_path = None
        if args.log_dir is not None:
            log_dir = Path(args.log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = str(log_dir / f"{args.player}-{args.mode}-seed{seed}.jsonl")

        play_and_record(
            player,
            seed=seed,
            mode=args.mode,
            added_delay_ms=args.delay_ms,
            max_steps=args.max_steps,
            repo_dir=REPO_DIR,
            no_commit=args.no_commit,
            no_push=args.no_push,
            sdk_package=sdk_package,
            sdk_version=sdk_version,
            record_video=video_path,
            log_path=log_path,
            notes=args.notes,
        )

    return 0


def bench_command(args: argparse.Namespace) -> int:
    players = parse_list(args.players)
    seeds = parse_seeds(args.seeds)
    modes = parse_list(args.modes)
    delays = parse_delays(args.delays)

    for name in players:
        if name not in PLAYERS:
            print(f"error: unknown player {name!r}", file=sys.stderr)
            return 1
    for mode in modes:
        if mode not in ("turn", "realtime"):
            print(f"error: unknown mode {mode!r}", file=sys.stderr)
            return 1

    matrix = build_matrix(players, seeds, modes, delays)

    existing = set()
    if args.skip_existing:
        results = load_results(REPO_DIR / RESULTS_FILENAME)
        existing = existing_keys(results)

    player_instances: dict[str, object] = {}
    ran = 0
    skipped = 0
    spent = 0.0
    dearest_game: dict[str, float] = {}  # the most expensive game so far, per player

    for game in matrix:
        if game.player not in player_instances:
            try:
                player_instances[game.player] = PLAYERS[game.player]()
            except MissingAPIKeyError as error:
                print(f"error: {error}", file=sys.stderr)
                return 1
        player = player_instances[game.player]

        key = game_key(game, args.max_steps, getattr(player, "version", None))
        if args.skip_existing and key in existing:
            skipped += 1
            print(
                f"skip player={game.player} seed={game.seed} mode={game.mode} "
                f"added_delay_ms={game.added_delay_ms:g} (already recorded)"
            )
            continue

        if args.max_cost_usd is not None:
            free = getattr(player, "provider", "none") in ("none", "local")
            next_game = dearest_game.get(game.player, 0.0 if free else DEFAULT_GAME_COST_USD)
            if spent + next_game > args.max_cost_usd:
                print(
                    f"stop: spent ${spent:.2f}; the next {game.player} game could cost "
                    f"${next_game:.2f}, over the cap of ${args.max_cost_usd:.2f}"
                )
                break

        sdk_package = SDK_PACKAGES.get(game.player)
        record = play_and_record(
            player,
            seed=game.seed,
            mode=game.mode,
            added_delay_ms=game.added_delay_ms,
            max_steps=args.max_steps,
            repo_dir=REPO_DIR,
            no_commit=args.no_commit,
            no_push=args.no_push,
            sdk_package=sdk_package,
            sdk_version=_package_version(sdk_package) if sdk_package else None,
            notes=args.notes,
        )
        ran += 1
        game_cost = record.get("cost_usd") or 0.0
        spent += game_cost
        dearest_game[game.player] = max(dearest_game.get(game.player, 0.0), game_cost)

    print(f"ran {ran} games, skipped {skipped} already recorded, spent ${spent:.2f}")
    return 0


def report_command(args: argparse.Namespace) -> int:
    results_path = Path(args.results) if args.results is not None else REPO_DIR / RESULTS_FILENAME
    out_dir = Path(args.out) if args.out is not None else REPO_DIR / "report"
    generate_report(results_path, out_dir)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return run_command(args)
    if args.command == "bench":
        return bench_command(args)
    if args.command == "verify":
        from invaders.verify import verify

        rows = verify(load_results(REPO_DIR / RESULTS_FILENAME), PLAYERS, args.limit)
        for row in rows:
            status = "match" if row["match"] else "MISMATCH"
            print(
                f"run {row['run']} {row['player']} seed {row['seed']}: recorded "
                f"{row['recorded']:g}, replayed {row['replayed']:g} {status}"
            )
        bad = sum(not row["match"] for row in rows)
        print(f"checked {len(rows)} runs, {bad} mismatches")
        return 1 if bad else 0
    if args.command == "diagnose":
        from invaders.diagnose import diagnose, summary

        seeds = parse_seeds(args.seeds)
        if any(seed > 99 for seed in seeds):
            print("error: diagnose runs on tuning seeds 1-99 only", file=sys.stderr)
            return 1
        rows = diagnose(PLAYERS[args.player], seeds)
        if args.per_game:
            for row in rows:
                print(row)
        print(summary(rows))
        return 0
    if args.command == "report":
        return report_command(args)
    parser.print_usage()
    return 1


if __name__ == "__main__":
    sys.exit(main())
