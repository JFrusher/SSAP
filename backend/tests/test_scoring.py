import itertools

import pytest

from backend.engine.models import Card
from backend.engine.rules import card_points, color_bonus

_ids = itertools.count()


def c(name: str, color: str = "dark_blue") -> Card:
    return Card(id=f"t{next(_ids)}", name=name, color="white" if name == "mermaid" else color)  # type: ignore[arg-type]


def cards(*names: str) -> list[Card]:
    return [c(n) for n in names]


@pytest.mark.parametrize("n,pts", [(1, 0), (2, 2), (3, 4), (4, 6), (5, 8), (6, 10)])
def test_shells(n: int, pts: int) -> None:
    assert card_points(cards(*["shell"] * n)) == pts


@pytest.mark.parametrize("n,pts", [(1, 0), (2, 3), (3, 6), (4, 9), (5, 12)])
def test_octopus(n: int, pts: int) -> None:
    assert card_points(cards(*["octopus"] * n)) == pts


@pytest.mark.parametrize("n,pts", [(1, 1), (2, 3), (3, 5)])
def test_penguins(n: int, pts: int) -> None:
    assert card_points(cards(*["penguin"] * n)) == pts


def test_sailors() -> None:
    assert card_points(cards("sailor")) == 0
    assert card_points(cards("sailor", "sailor")) == 5


def test_duo_pairs() -> None:
    assert card_points(cards("crab", "crab", "crab")) == 1
    assert card_points(cards("boat", "boat", "fish", "fish")) == 2
    assert card_points(cards("shark", "shark", "swimmer")) == 1
    assert card_points(cards("shark", "shark")) == 0


def test_multipliers_count_cards_but_score_nothing_alone() -> None:
    assert card_points(cards("lighthouse")) == 0
    assert card_points(cards("lighthouse", "boat", "boat", "boat")) == 1 + 3
    assert card_points(cards("shoal", "fish")) == 1
    assert card_points(cards("colony", "penguin", "penguin")) == 3 + 4
    assert card_points(cards("captain", "sailor", "sailor")) == 5 + 6


def test_mermaids_take_successive_colours() -> None:
    hand = [c("shell", "pink"), c("shell", "pink"), c("shell", "pink"), c("crab", "black"), c("crab", "black"), c("boat", "yellow")]
    base = 4 + 1  # three shells + crab pair
    assert card_points(hand + cards("mermaid")) == base + 3
    assert card_points(hand + cards("mermaid", "mermaid")) == base + 3 + 2
    assert card_points(hand + cards("mermaid", "mermaid", "mermaid")) == base + 3 + 2 + 1
    assert card_points(cards("mermaid")) == 0


def test_color_bonus_ignores_mermaids() -> None:
    hand = [c("shell", "pink"), c("crab", "pink"), c("boat", "grey")] + cards("mermaid", "mermaid", "mermaid")
    assert color_bonus(hand) == 2
