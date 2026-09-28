"""Command-line interface: play games and record their results."""

import argparse
import sys
from pathlib import Path

from invaders.harness import run_game
from invaders.players.code_player import CodePlayer
from invaders.players.random_player import RandomPlayer
from invaders.results import build_model_entry, record_and_commit

# Add one entry here to support a new player; the CLI needs no other change.
PLAYERS = {
    "code": CodePlayer,
    "random": RandomPlayer,
}

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
    run.add_argument("--no-commit", action="store_true")

    return parser


def run_command(args: argparse.Namespace) -> int:
    seeds = parse_seeds(args.seeds)
    player_cls = PLAYERS[args.player]

    for seed in seeds:
        player = player_cls()

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

        record = run_game(
            player,
            seed=seed,
            mode=args.mode,
            added_delay_ms=args.delay_ms,
            max_steps=args.max_steps,
            record_video=video_path,
            log_path=log_path,
        )

        print(
            f"player={record['player']} seed={record['seed']} mode={record['mode']} "
            f"score={record['score']} steps={record['steps']} decisions={record['decisions']} "
            f"latency_p50={record['latency_ms_p50']:.2f}ms latency_p95={record['latency_ms_p95']:.2f}ms"
        )

        if not args.no_commit:
            model = build_model_entry(player, served_model=record["served_model"])
            record_and_commit(record, REPO_DIR, push=not args.no_push, model=model)

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return run_command(args)
    parser.print_usage()
    return 1


if __name__ == "__main__":
    sys.exit(main())
