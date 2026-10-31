"""Full-information Sea Salt & Paper simulator.

Each seat keeps its own hero-perspective GameState, advanced only through rules.apply_action,
so bots see exactly what the live app would see and every move is consistency-checked.
"""
import random
from dataclasses import dataclass, field

from backend.engine.models import DECK_COMPOSITION, NON_WHITE_COLORS, Card, CardName, Color, GameState, RoundResult
from backend.engine.rules import (
    Action, DrawDeck, EndTurn, PlayDuo, ResolveRound, StartRound, TakeDiscard, apply_action, new_game,
)
from backend.arena.bots import Bot, DuoChoice

MAX_ROUNDS = 40  # guard: rounds where the deck runs out score nothing and could repeat forever
MAX_ACTIONS_PER_ROUND = 400


def make_deck(rng: random.Random) -> list[Card]:
    # shortcut: real per-card colours are unknown, so each card gets a uniform random colour per game;
    # upgrade by loading a measured colour table once colours have been logged from real games.
    cards = []
    for name, n in DECK_COMPOSITION.items():
        for i in range(n):
            color: Color = "white" if name == "mermaid" else rng.choice(NON_WHITE_COLORS)
            cards.append(Card(id=f"{name}{i}", name=name, color=color))
    rng.shuffle(cards)
    return cards


@dataclass
class Table:
    views: list[GameState]
    deck: list[Card] = field(default_factory=list)  # deck[-1] is the top card
    hands: list[list[Card]] = field(default_factory=list)  # true hands by seat

    @property
    def ref(self) -> GameState:
        return self.views[0]

    def seat(self, player_id: str) -> int:
        return int(player_id[1:])

    def apply_all(self, public: Action, private: dict[int, Action] | None = None) -> None:
        """Apply an action to every seat's view; `private` overrides the action for seats that see more."""
        private = private or {}
        self.views = [apply_action(v, private.get(i, public)) for i, v in enumerate(self.views)]


def _duo_cards(hand: list[Card], names: tuple[CardName, CardName]) -> tuple[Card, Card]:
    first = next(c for c in hand if c.name == names[0])
    second = next(c for c in hand if c.name == names[1] and c.id != first.id)
    return first, second


DUO_NAMES: dict[str, tuple[CardName, CardName]] = {
    "crab": ("crab", "crab"), "boat": ("boat", "boat"), "fish": ("fish", "fish"), "shark": ("shark", "swimmer"),
}


def _turn(t: Table, bots: list[Bot], rng: random.Random) -> None:
    pid = t.ref.active_player_id
    s = t.seat(pid)
    bot, view = bots[s], t.views[s]

    # draw
    source = bot.choose_draw(view, rng)
    if source == "deck":
        drawn = [t.deck.pop() for _ in range(min(2, len(t.deck)))]
        if len(drawn) == 1:
            keep, pile, discarded = drawn[0], None, None
        else:
            idx, pile = bot.choose_keep(view, drawn[0], drawn[1], rng)
            keep, discarded = drawn[idx], drawn[1 - idx]
        t.hands[s].append(keep)
        t.apply_all(DrawDeck(discarded=discarded, pile=pile), {s: DrawDeck(kept=keep, discarded=discarded, pile=pile)})
    else:
        top = t.ref.discard_ledger.top(source)
        assert top is not None
        t.hands[s].append(top)
        t.apply_all(TakeDiscard(pile=source))

    # duos
    while (choice := bot.choose_duo(t.views[s], rng)) is not None:
        _play_duo(t, s, choice, rng)

    t.apply_all(EndTurn(call=bot.choose_call(t.views[s], rng)))


def _play_duo(t: Table, s: int, choice: DuoChoice, rng: random.Random) -> None:
    c1, c2 = _duo_cards(t.hands[s], DUO_NAMES[choice.duo])
    t.hands[s] = [c for c in t.hands[s] if c.id not in (c1.id, c2.id)]
    base = PlayDuo(cards=(c1, c2))
    if choice.duo == "boat":
        t.apply_all(base)
    elif choice.duo == "crab":
        act = base
        if choice.crab_pile is not None:
            card = next(c for c in t.ref.discard_ledger.pile(choice.crab_pile) if c.id == choice.crab_card_id)
            t.hands[s].append(card)
            act = base.model_copy(update={"crab_pile": choice.crab_pile, "crab_card_id": card.id})
        t.apply_all(act)
    elif choice.duo == "fish":
        if not t.deck:
            t.apply_all(base)
            return
        card = t.deck.pop()
        t.hands[s].append(card)
        t.apply_all(base, {s: base.model_copy(update={"fish_card": card})})
    else:
        victim_id = choice.steal_from
        if victim_id is None:
            t.apply_all(base)
            return
        v = t.seat(victim_id)
        card = rng.choice(t.hands[v])
        t.hands[v].remove(card)
        t.hands[s].append(card)
        public = base.model_copy(update={"steal_from": victim_id})
        seen = public.model_copy(update={"stolen_card": card})
        t.apply_all(public, {s: seen, v: seen})


def _resolve(t: Table) -> None:
    actions: dict[int, Action] = {}
    for i, view in enumerate(t.views):
        if view.round_end_reason == "deck_empty":
            actions[i] = ResolveRound()
            continue
        revealed = {}
        for p in view.players:
            if p.player_id == view.hero_id:
                continue
            known = {c.id for c in p.known_hand}
            revealed[p.player_id] = [c for c in t.hands[t.seat(p.player_id)] if c.id not in known]
        actions[i] = ResolveRound(revealed=revealed)
    t.apply_all(actions[0], actions)
    scores = {tuple(p.current_score for p in v.players) for v in t.views}
    assert len(scores) == 1, f"seat views disagree on scores: {scores}"


def play_game(bots: list[Bot], rng: random.Random) -> tuple[int | None, list[RoundResult]]:
    """Play one full game; returns (winning seat or None if MAX_ROUNDS is hit, round history)."""
    n = len(bots)
    t = Table(views=[new_game([f"s{i}" for i in range(n)], i) for i in range(n)])
    first = rng.randrange(n)
    for _ in range(MAX_ROUNDS):
        t.deck = make_deck(rng)
        t.hands = [[] for _ in range(n)]
        a, b = t.deck.pop(), t.deck.pop()
        t.apply_all(StartRound(pile_a=a, pile_b=b, first_player_id=f"p{first}"))
        for _ in range(MAX_ACTIONS_PER_ROUND):
            if t.ref.phase == "round_end":
                break
            _turn(t, bots, rng)
        else:
            raise RuntimeError("round did not end")
        ender = t.seat(t.ref.last_chance_caller or t.ref.active_player_id)
        _resolve(t)
        if t.ref.phase == "game_over":
            return t.seat(t.ref.winner_id), t.ref.history  # type: ignore[arg-type]
        first = (ender + 1) % n
    return None, t.ref.history

