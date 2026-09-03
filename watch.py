"""Watch a single match round by round.

A viewing tool, not part of the experiment. It imports the same strategy
functions the tournament uses, so what you see here is exactly what produced
the numbers in the leaderboard -- there is no second implementation that
could drift.

Usage
-----
    python watch.py --list
        Show the strategy names you can pass.

    python watch.py "Tit-for-Tat" "Always Defect"
        Play one match and print every round.

    python watch.py "Grim Trigger" "Random" --rounds 30
        Shorter match, easier to read.

    python watch.py "Grim Trigger" "Random" --compare "Tit-for-Tat"
        Play two different challengers against the SAME opponent, drawing the
        same random numbers, and show the two matches side by side. This is
        how to see why Grim and Tit-for-Tat score differently against Random
        while scoring identically against everyone else.

    python watch.py "Pavlov" "Always Defect" --rounds 12 --slow 0.4
        Print a round at a time with a pause, so it plays out in front of you.

    python watch.py "Tit-for-Tat" "Random" --seed 7
        Same match, different luck.
"""

from __future__ import annotations

import argparse
import sys
import time

import numpy as np

from config import DEFAULT_CONFIG, Payoffs
from strategies import STRATEGIES, Move, Strategy

# How each pair of moves reads in the round-by-round output.
OUTCOME_LABEL = {
    (Move.COOPERATE, Move.COOPERATE): "both cooperate",
    (Move.COOPERATE, Move.DEFECT): "exploited",
    (Move.DEFECT, Move.COOPERATE): "exploiting",
    (Move.DEFECT, Move.DEFECT): "both defect",
}


def resolve(name: str) -> Strategy:
    """Look a strategy up by name, with a helpful error if it is not there."""
    if name not in STRATEGIES:
        available = "\n  ".join(STRATEGIES)
        raise SystemExit(f"Unknown strategy {name!r}. Available:\n  {available}")
    return STRATEGIES[name]


def play_and_record(
    a: Strategy,
    b: Strategy,
    rounds: int,
    payoffs: Payoffs,
    rng: np.random.Generator,
) -> list[dict]:
    """Play a match, keeping one record per round rather than only the total.

    Mirrors `tournament.play_match` exactly -- both moves are chosen from the
    history *before* the round, so neither player sees the other's current
    move -- but returns the per-round detail the tournament has no use for.
    """
    rng_a, rng_b = rng.spawn(2)
    history_a: list[Move] = []
    history_b: list[Move] = []
    total_a = 0.0
    total_b = 0.0
    log: list[dict] = []

    for number in range(1, rounds + 1):
        move_a = a(history_a, history_b, rng_a)
        move_b = b(history_b, history_a, rng_b)
        gain_a = payoffs.payoff_for(move_a, move_b)
        gain_b = payoffs.payoff_for(move_b, move_a)
        total_a += gain_a
        total_b += gain_b
        history_a.append(move_a)
        history_b.append(move_b)
        log.append(
            {
                "round": number,
                "move_a": move_a,
                "move_b": move_b,
                "gain_a": gain_a,
                "gain_b": gain_b,
                "total_a": total_a,
                "total_b": total_b,
                "mean_a": total_a / number,
                "outcome": OUTCOME_LABEL[(move_a, move_b)],
            }
        )
    return log


def print_match(name_a: str, name_b: str, log: list[dict], slow: float) -> None:
    """Print one match, one line per round."""
    print()
    print(f"{name_a}  vs  {name_b}")
    print("-" * 64)
    print(f"{'rd':>4}  {'them':>5}  {'me':>4}  {'got':>5}  {'avg':>6}   what happened")
    print("-" * 64)
    for row in log:
        print(
            f"{row['round']:>4}  "
            f"{str(row['move_b']):>5}  "
            f"{str(row['move_a']):>4}  "
            f"{row['gain_a']:>5.0f}  "
            f"{row['mean_a']:>6.2f}   "
            f"{row['outcome']}"
        )
        if slow:
            sys.stdout.flush()
            time.sleep(slow)
    last = log[-1]
    print("-" * 64)
    print(
        f"{name_a}: {last['total_a']:.0f} total, {last['mean_a']:.3f} per round   |   "
        f"{name_b}: {last['total_b']:.0f} total, "
        f"{last['total_b'] / last['round']:.3f} per round"
    )


def print_comparison(
    name_a: str, log_a: list[dict], name_c: str, log_c: list[dict], opponent: str
) -> None:
    """Two challengers against the same opponent, on the same random draws."""
    print()
    print(f"Both challengers against {opponent}, identical random draws.")
    print("=" * 72)
    print(
        f"{'rd':>4}  {opponent[:10]:>10}  |  "
        f"{name_a[:12]:>12} {'got':>4} {'avg':>6}  |  "
        f"{name_c[:12]:>12} {'got':>4} {'avg':>6}"
    )
    print("=" * 72)
    for row_a, row_c in zip(log_a, log_c):
        # Sanity: the shared opponent must be playing the same match in both.
        marker = " " if row_a["move_b"] is row_c["move_b"] else " !DIVERGED!"
        print(
            f"{row_a['round']:>4}  {str(row_a['move_b']):>10}  |  "
            f"{str(row_a['move_a']):>12} {row_a['gain_a']:>4.0f} {row_a['mean_a']:>6.2f}  |  "
            f"{str(row_c['move_a']):>12} {row_c['gain_a']:>4.0f} {row_c['mean_a']:>6.2f}"
            f"{marker}"
        )
    print("=" * 72)
    end_a, end_c = log_a[-1], log_c[-1]
    print(
        f"{name_a}: {end_a['mean_a']:.3f} per round   "
        f"{name_c}: {end_c['mean_a']:.3f} per round   "
        f"difference: {end_a['mean_a'] - end_c['mean_a']:+.3f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Watch one Iterated Prisoner's Dilemma match round by round.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("player", nargs="?", help="the strategy whose view you see")
    parser.add_argument("opponent", nargs="?", help="who it plays against")
    parser.add_argument(
        "--compare",
        metavar="STRATEGY",
        help="second challenger, played against the same opponent on the same draws",
    )
    parser.add_argument("--rounds", type=int, default=25, help="rounds to play (default 25)")
    parser.add_argument(
        "--seed", type=int, default=DEFAULT_CONFIG.root_seed, help="random seed"
    )
    parser.add_argument(
        "--slow", type=float, default=0.0, metavar="SECONDS",
        help="pause between rounds so the match plays out (e.g. 0.3)",
    )
    parser.add_argument("--list", action="store_true", help="list strategy names and exit")
    args = parser.parse_args()

    if args.list or not args.player:
        print("Strategies:")
        for name in STRATEGIES:
            print(f"  {name}")
        print('\nExample:\n  python watch.py "Grim Trigger" "Random" --compare "Tit-for-Tat"')
        return

    if not args.opponent:
        raise SystemExit("Give two strategies, or --list to see the names.")

    payoffs = DEFAULT_CONFIG.payoffs
    player = resolve(args.player)
    opponent = resolve(args.opponent)

    log = play_and_record(
        player, opponent, args.rounds, payoffs, np.random.default_rng(args.seed)
    )

    if args.compare:
        challenger = resolve(args.compare)
        # Same seed means the opponent's random stream is regenerated
        # identically, so the two challengers face the very same behaviour.
        log_c = play_and_record(
            challenger, opponent, args.rounds, payoffs, np.random.default_rng(args.seed)
        )
        print_comparison(args.player, log, args.compare, log_c, args.opponent)
    else:
        print_match(args.player, args.opponent, log, args.slow)


if __name__ == "__main__":
    main()
