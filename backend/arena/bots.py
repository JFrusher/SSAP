"""Arena bots. A bot only ever sees its own seat's hero-perspective GameState."""
import random
from collections import Counter
from dataclasses import dataclass
from typing import Literal, Protocol

from backend.engine.belief_tracker import OpponentBeliefTracker
from backend.engine.particle_belief import ParticleBelief, learned_beta
from backend.engine.models import END_ROUND_MIN_POINTS, Card, GameState, Pile
from backend.engine.rules import all_cards, card_points
from backend.solver import fastsim, ismcts
from backend.solver.ev_calculator import Beliefs, BeliefFactory, draw_options, duo_options, keep_advice, simulate

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
    factory: BeliefFactory = OpponentBeliefTracker

    def __init__(self) -> None:
        self._cache: tuple[int, Beliefs] | None = None

    def beliefs(self, view: GameState) -> Beliefs:
        if self._cache is None or self._cache[0] != id(view):  # views are immutable: one build per state
            self._cache = (id(view), self.factory(view))
        return self._cache[1]

    def choose_draw(self, view: GameState, rng: random.Random) -> Source:
        opts = draw_options(view, self.beliefs(view).deck)
        return max(opts, key=lambda o: o.ev).source

    def choose_keep(self, view: GameState, first: Card, second: Card, rng: random.Random) -> tuple[int, Pile]:
        # shortcut: the engine has no discard-pile advice yet, so the pile is random among legal ones.
        return keep_advice(view, first, second, lambda _: self.beliefs(view)).keep_index, rng.choice(discard_piles(view))

    def choose_duo(self, view: GameState, rng: random.Random) -> DuoChoice | None:
        opts = duo_options(view, self.beliefs(view))
        if not opts:
            return None
        o = opts[0]  # the engine advises playing every duo
        return DuoChoice(o.duo, crab_pile=o.crab_pile, crab_card_id=o.crab_card_id, steal_from=o.steal_from)

    def choose_call(self, view: GameState, rng: random.Random) -> Call:
        if not can_call(view):
            return None
        _, advice = simulate(view, self.beliefs(view))
        assert advice is not None
        return None if advice.best == "continue" else advice.best


class ParticleGreedyBot(GreedyBot):
    """Greedy decisions on particle-filter beliefs (phase 2)."""

    name = "particle"
    factory = ParticleBelief


class LearnedBetaBot(GreedyBot):
    """Phase 5: greedy decisions on particle beliefs with per-opponent learned rationality."""

    name = "learned"
    factory = staticmethod(learned_beta)  # type: ignore[assignment]


class IsmctsBot:
    """Phase 3: information-set Monte Carlo search over the hero's decisions."""

    name = "ismcts"
    evaluate: ismcts.Evaluator = staticmethod(ismcts.margin_value)  # type: ignore[assignment]

    def __init__(self) -> None:
        self._call: tuple[int, Call] | None = None

    def _search(self, view: GameState, drawn: tuple[Card, Card] | None = None) -> ismcts.RootAction:
        return ismcts.best(ismcts.search(view, drawn, evaluate=self.evaluate))

    def choose_draw(self, view: GameState, rng: random.Random) -> Source:
        return self._search(view)[1]

    def choose_keep(self, view: GameState, first: Card, second: Card, rng: random.Random) -> tuple[int, Pile]:
        a = self._search(view, (first, second))
        return a[1], a[2]

    def choose_duo(self, view: GameState, rng: random.Random) -> DuoChoice | None:
        a = self._search(view)
        if a[0] == "end":
            self._call = (id(view), a[1])
            return None
        hero = [(c.name, c.color) for c in view.hero.known_hand + view.hero.played_duos]
        if a[1] == "crab":  # same target rule as the rollout policy: the best-valued pile card
            cards = [(fastsim.value(hero, (c.name, c.color)), p, c.id) for p in ("a", "b") for c in view.discard_ledger.pile(p)]  # type: ignore[arg-type]
            if cards:
                _, pile, cid = max(cards)
                return DuoChoice("crab", crab_pile=pile, crab_card_id=cid)  # type: ignore[arg-type]
        if a[1] == "shark":
            targets = [p for p in view.opponents if p.hand_size > 0]
            return DuoChoice("shark", steal_from=max(targets, key=lambda p: p.hand_size).player_id if targets else None)
        return DuoChoice(a[1])

    def choose_call(self, view: GameState, rng: random.Random) -> Call:
        assert self._call is not None and self._call[0] == id(view), "choose_duo decides the call for this view"
        return self._call[1]


class IsmctsWinBot(IsmctsBot):
    """Phase 4: the same search, valuing outcomes by P(win the game) instead of round margin."""

    name = "ismcts_win"
    evaluate = staticmethod(ismcts.win_value)  # type: ignore[assignment]


BOTS: dict[str, type] = {"random": RandomBot, "greedy": GreedyBot, "particle": ParticleGreedyBot, "ismcts": IsmctsBot, "ismcts_win": IsmctsWinBot, "learned": LearnedBetaBot}
