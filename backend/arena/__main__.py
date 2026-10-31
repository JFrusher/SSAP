"""python -m backend.arena --bots greedy,random --games 2000 --seed 1"""
import argparse
import math
import random
from multiprocessing import Pool

from backend.arena.bots import BOTS
from backend.arena.sim import play_game


def wilson(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a win rate."""
    if n == 0:
        return 0.0, 1.0
    p = wins / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def run_one(args: tuple[list[str], int, int]) -> int | None:
    """Play game `i`; seats rotate by i so every bot plays every seat equally. Returns the winning bot index."""
    names, seed, i = args
    n = len(names)
    order = [(j + i) % n for j in range(n)]  # order[seat] = bot index
    seat = play_game([BOTS[names[b]]() for b in order], random.Random(seed * 1_000_003 + i))
    return None if seat is None else order[seat]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bots", required=True, help="comma-separated, 2-4 of: " + ", ".join(BOTS))
    ap.add_argument("--games", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    names = a.bots.split(",")
    if not 2 <= len(names) <= 4 or any(b not in BOTS for b in names):
        raise SystemExit(f"--bots needs 2-4 of {list(BOTS)}")
    with Pool(a.workers) as pool:
        results = pool.map(run_one, [(names, a.seed, i) for i in range(a.games)], chunksize=8)
    print(f"{a.games} games, seed {a.seed}, seats rotated")
    for b, name in enumerate(names):
        wins = sum(r == b for r in results)
        lo, hi = wilson(wins, a.games)
        print(f"  [{b}] {name:8s} wins {wins:5d}  {wins / a.games:6.1%}  95% CI [{lo:.1%}, {hi:.1%}]")
    print(f"  unfinished (hit round cap): {sum(r is None for r in results)}")


if __name__ == "__main__":
    main()
