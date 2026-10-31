"""Arena bots. A bot only ever sees its own seat's hero-perspective GameState."""
import random
from collections import Counter
from dataclasses import dataclass
from typing import Literal, Protocol

from backend.engine.belief_tracker import OpponentBeliefTracker
from backend.engine.models import END_ROUND_MIN_POINTS, Card, GameState, Pile
from backend.engine.rules import all_cards, card_points
from backend.solver.ev_calculator import draw_options, duo_options, keep_advice, simulate

Source = Literal["deck", "a", "b"]
Call = Literal["stop", "last_chance"] | None


@dataclass(frozen=True)
class DuoChoice:
    duo: Literal["crab", "boat", "fish", "shark"]
    crab_pile: Pile | None = None
    crab_card_id: str | None = None
    steal_from: str | None = None


class Bot(Protocol):
    name: str

    def choose_draw(self, view: GameState, rng: random.Random) -> Source: ...
    def choose_keep(self, view: GameState, first: Card, second: Card, rng: random.Random) -> tuple[int, Pile]: ...
    def choose_duo(self, view: GameState, rng: random.Random) -> DuoChoice | None: ...
    def choose_call(self, view: GameState, rng: random.Random) -> Call: ...


def legal_sources(view: GameState) -> list[Source]:
    out: list[Source] = ["deck"] if view.deck_count > 0 else []
    return out + [p for p in ("a", "b") if view.discard_ledger.top(p) is not None]  # type: ignore[misc]


def discard_piles(view: GameState) -> list[Pile]:
    empty = [p for p in ("a", "b") if view.discard_ledger.top(p) is None]  # type: ignore[misc]
    return empty or ["a", "b"]  # rule: an empty pile must be filled first


def playable_duos(view: GameState) -> list[Literal["crab", "boat", "fish", "shark"]]:
    n = Counter(c.name for c in view.hero.known_hand)
    out: list[Literal["crab", "boat", "fish", "shark"]] = [d for d in ("crab", "boat", "fish") if n[d] >= 2]  # type: ignore[misc]
    if n["shark"] and n["swimmer"]:
        out.append("shark")
    return out


def can_call(view: GameState) -> bool:
    return view.last_chance_caller is None and card_points(all_cards(view.hero)) >= END_ROUND_MIN_POINTS


class RandomBot:
    name = "random"

    def choose_draw(self, view: GameState, rng: random.Random) -> Source:
        return rng.choice(legal_sources(view))

    def choose_keep(self, view: GameState, first: Card, second: Card, rng: random.Random) -> tuple[int, Pile]:
        return rng.randrange(2), rng.choice(discard_piles(view))

    def choose_duo(self, view: GameState, rng: random.Random) -> DuoChoice | None:
        duos = playable_duos(view)
        if not duos or rng.random() < 0.5:
            return None
        duo = rng.choice(duos)
        if duo == "crab":
            cards = [(p, c.id) for p in ("a", "b") for c in view.discard_ledger.pile(p)]  # type: ignore[arg-type]
            if cards:
                pile, cid = rng.choice(cards)
                return DuoChoice(duo, crab_pile=pile, crab_card_id=cid)  # type: ignore[arg-type]
        if duo == "shark":
            targets = [p.player_id for p in view.opponents if p.hand_size > 0]
            return DuoChoice(duo, steal_from=rng.choice(targets) if targets else None)
        return DuoChoice(duo)

    def choose_call(self, view: GameState, rng: random.Random) -> Call:
        return rng.choice([None, "stop", "last_chance"]) if can_call(view) else None


class GreedyBot:
    """The engine currently shipped in /api/apply (backend/solver/ev_calculator.py)."""

    name = "greedy"

    def choose_draw(self, view: GameState, rng: random.Random) -> Source:
        opts = draw_options(view, OpponentBeliefTracker(view).deck)
        return max(opts, key=lambda o: o.ev).source

    def choose_keep(self, view: GameState, first: Card, second: Card, rng: random.Random) -> tuple[int, Pile]:
        # shortcut: the engine has no discard-pile advice yet, so the pile is random among legal ones.
        return keep_advice(view, first, second).keep_index, rng.choice(discard_piles(view))

    def choose_duo(self, view: GameState, rng: random.Random) -> DuoChoice | None:
        opts = duo_options(view, OpponentBeliefTracker(view))
        if not opts:
            return None
        o = opts[0]  # the engine advises playing every duo
        return DuoChoice(o.duo, crab_pile=o.crab_pile, crab_card_id=o.crab_card_id, steal_from=o.steal_from)

    def choose_call(self, view: GameState, rng: random.Random) -> Call:
        if not can_call(view):
            return None
        _, advice = simulate(view, OpponentBeliefTracker(view))
        assert advice is not None
        return None if advice.best == "continue" else advice.best


BOTS: dict[str, type] = {"random": RandomBot, "greedy": GreedyBot}
