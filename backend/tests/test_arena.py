import random

import pytest

from backend.arena.__main__ import run_one, wilson
from backend.arena.bots import GreedyBot, RandomBot
from backend.arena.sim import play_game


def test_wilson_interval() -> None:
    lo, hi = wilson(50, 100)
    assert lo == pytest.approx(0.4038, abs=1e-3) and hi == pytest.approx(0.5962, abs=1e-3)


@pytest.mark.parametrize("seats", [2, 3, 4])
def test_random_games_finish_with_consistent_views(seats: int) -> None:
    # play_game asserts every seat's view agrees on scores and rules.apply_action checks deck consistency each move
    winner = play_game([RandomBot() for _ in range(seats)], random.Random(seats))
    assert winner is None or 0 <= winner < seats


def test_games_are_reproducible_from_seed() -> None:
    assert [run_one((["random", "random"], 7, i)) for i in range(5)] == [run_one((["random", "random"], 7, i)) for i in range(5)]


def test_greedy_beats_random() -> None:
    wins = sum(play_game([GreedyBot(), RandomBot()], random.Random(i)) == 0 for i in range(6))
    assert wins >= 5
