"""Build backend/solver/win_model.json: P(win game) from (my score, best opponent score) at a round start.

python -m backend.arena.value_table --games 3000 --seed 1

Self-play with the greedy bot; one logistic model per player count, fitted by Newton's method.
"""
import argparse
import json
import math
import random
from multiprocessing import Pool
from pathlib import Path

from backend.arena.bots import GreedyBot
from backend.arena.sim import play_game
from backend.engine.models import TARGET_SCORE
from backend.solver.ismcts import features

OUT = Path(__file__).resolve().parent.parent / "solver" / "win_model.json"


def _game(args: tuple[int, int, int]) -> list[tuple[list[float], int]]:
    n, seed, i = args
    winner, history = play_game([GreedyBot() for _ in range(n)], random.Random(seed * 7_919 + i))
    if winner is None:
        return []
    target = TARGET_SCORE[n]
    totals = {f"p{s}": 0 for s in range(n)}
    rows = []
    for r in history:  # one row per seat per round start
        for s in range(n):
            pid = f"p{s}"
            best = max(v for k, v in totals.items() if k != pid)
            rows.append((features(totals[pid], best, target), int(winner == s)))
        for k, v in r.awarded.items():
            totals[k] += v
    return rows


def fit(rows: list[tuple[list[float], int]], iters: int = 25) -> list[float]:
    """Logistic regression by Newton's method (4 parameters, so a hand-written solve is enough)."""
    k = len(rows[0][0])
    w = [0.0] * k
    for _ in range(iters):
        grad = [0.0] * k
        hess = [[1e-6 * (i == j) for j in range(k)] for i in range(k)]
        for x, y in rows:
            p = 1 / (1 + math.exp(-sum(a * b for a, b in zip(w, x))))
            for i in range(k):
                grad[i] += (y - p) * x[i]
                for j in range(k):
                    hess[i][j] += p * (1 - p) * x[i] * x[j]
        w = [a + b for a, b in zip(w, _solve(hess, grad))]
    return w


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[piv] = m[piv], m[c]
        for r in range(n):
            if r != c:
                f = m[r][c] / m[c][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c])]
    return [m[i][n] / m[i][i] for i in range(n)]


def log_loss(w: list[float], rows: list[tuple[list[float], int]]) -> float:
    total = 0.0
    for x, y in rows:
        p = min(1 - 1e-9, max(1e-9, 1 / (1 + math.exp(-sum(a * b for a, b in zip(w, x))))))
        total -= y * math.log(p) + (1 - y) * math.log(1 - p)
    return total / len(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    model = {}
    for n in (2, 3, 4):
        games = a.games if n == 2 else a.games // 2
        with Pool(4) as pool:
            rows = [r for g in pool.map(_game, [(n, a.seed, i) for i in range(games)], chunksize=16) for r in g]
        rng = random.Random(0)
        rng.shuffle(rows)
        cut = len(rows) * 4 // 5
        w = fit(rows[:cut])
        base = sum(y for _, y in rows[cut:]) / len(rows[cut:])
        base_loss = -(base * math.log(base) + (1 - base) * math.log(1 - base))
        print(f"{n} players: {games} games, {len(rows)} rows, held-out log-loss {log_loss(w, rows[cut:]):.4f} vs base-rate {base_loss:.4f}")
        model[str(n)] = {"weights": w, "target": TARGET_SCORE[n]}
    OUT.write_text(json.dumps(model, indent=1) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
