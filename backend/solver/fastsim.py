"""Fast full-information round simulator for search rollouts (plain lists, no pydantic copies).

Same rules as backend/engine/rules.py; the arena (which runs every move through rules.py) is the check
that decisions made with it are sound.
"""
import random
from collections import Counter
from dataclasses import dataclass, field

from backend.engine.models import DECK_COMPOSITION, END_ROUND_MIN_POINTS, NON_WHITE_COLORS, CardName, Color
from backend.engine.rules import color_bonus_counts, score_counts

FCard = tuple[CardName, Color]


def points(cards: list[FCard]) -> int:
    return score_counts(Counter(c[0] for c in cards), Counter(c[1] for c in cards))


def bonus(cards: list[FCard]) -> int:
    return color_bonus_counts(Counter(c[1] for c in cards))


def value(cards: list[FCard], card: FCard) -> float:
    """Points now + half of what a second copy would add (same opponent model as the particle filter)."""
    base = points(cards)
    nxt = cards + [card]
    if sum(c[0] == card[0] for c in nxt) > DECK_COMPOSITION[card[0]]:
        # shortcut: a sampled hand can include a copy of a card the hero has just drawn but not yet recorded;
        # such a hand can't gain it, so it is worth 0. Upgrade by conditioning samples on the drawn cards.
        return 0.0
    now = points(nxt)
    if sum(c[0] == card[0] for c in nxt) + 1 > DECK_COMPOSITION[card[0]]:
        return now - base
    return now - base + 0.5 * max(0, points(nxt + [card]) - now)


def random_color(rng: random.Random, name: CardName) -> Color:
    return "white" if name == "mermaid" else rng.choice(NON_WHITE_COLORS)


@dataclass
class World:
    hands: list[list[FCard]]
    played: list[list[FCard]]
    piles: dict[str, list[FCard]]
    deck: list[FCard]  # deck[-1] is the top
    active: int
    caller: int | None = None
    queue: list[int] = field(default_factory=list)
    extra: bool = False

    def mine(self, s: int) -> list[FCard]:
        return self.hands[s] + self.played[s]

    def copy(self) -> "World":
        return World([list(h) for h in self.hands], [list(p) for p in self.played],
                     {k: list(v) for k, v in self.piles.items()}, list(self.deck), self.active,
                     self.caller, list(self.queue), self.extra)


# ------------------------------------------------------------ primitives (shared by search root and rollouts)

def draw_pile(w: World, s: int, pile: str) -> None:
    w.hands[s].append(w.piles[pile].pop())


def draw_deck(w: World, s: int, keep: int | None, pile: str | None, rng: random.Random) -> None:
    """Take two cards; keep index `keep` (None = policy) and discard onto `pile` (None = policy)."""
    drawn = [w.deck.pop() for _ in range(min(2, len(w.deck)))]
    if len(drawn) == 1:
        w.hands[s].append(drawn[0])
        return
    if keep is None:
        keep = 0 if value(w.mine(s), drawn[0]) >= value(w.mine(s), drawn[1]) else 1
    empty = [p for p in ("a", "b") if not w.piles[p]]
    if pile is None:
        pile = empty[0] if empty else rng.choice(("a", "b"))
    w.hands[s].append(drawn[keep])
    w.piles[pile].append(drawn[1 - keep])


def duos_in_hand(w: World, s: int) -> list[str]:
    n = Counter(c[0] for c in w.hands[s])
    out = [d for d in ("crab", "boat", "fish") if n[d] >= 2]
    return out + (["shark"] if n["shark"] and n["swimmer"] else [])


def play_duo(w: World, s: int, duo: str, rng: random.Random) -> None:
    names = ("shark", "swimmer") if duo == "shark" else (duo, duo)
    for name in names:
        card = next(c for c in w.hands[s] if c[0] == name)
        w.hands[s].remove(card)
        w.played[s].append(card)
    if duo == "boat":
        w.extra = True
    elif duo == "crab":
        cards = [(value(w.mine(s), c), p, i) for p in ("a", "b") for i, c in enumerate(w.piles[p])]
        if cards:
            _, p, i = max(cards)
            w.hands[s].append(w.piles[p].pop(i))
    elif duo == "fish":
        if w.deck:
            w.hands[s].append(w.deck.pop())
    else:
        victims = [v for v in range(len(w.hands)) if v != s and w.hands[v]]
        if victims:
            v = max(victims, key=lambda v: len(w.hands[v]))
            w.hands[s].append(w.hands[v].pop(rng.randrange(len(w.hands[v]))))


def end_turn(w: World, s: int, call: str | None) -> str | None:
    """Returns the round-end reason, or None if play continues."""
    n = len(w.hands)
    if call == "stop":
        return "stop"
    if call == "last_chance":
        w.caller, w.queue, w.extra = s, [(s + k) % n for k in range(1, n)], False
    if not w.deck:
        return "deck_empty"
    if w.extra:
        w.extra = False
        return None
    if w.caller is not None:
        if not w.queue:
            return "last_chance"
        w.active = w.queue.pop(0)
        return None
    w.active = (s + 1) % n
    return None


def can_call(w: World, s: int) -> bool:
    return w.caller is None and points(w.mine(s)) >= END_ROUND_MIN_POINTS


# ------------------------------------------------------------ rollout policy

def policy_draw(w: World, s: int, rng: random.Random) -> None:
    tops = [(value(w.mine(s), w.piles[p][-1]), p) for p in ("a", "b") if w.piles[p]]
    best = max(tops, default=(-1.0, None))
    if best[1] is not None and (best[0] >= 1.0 or not w.deck):
        draw_pile(w, s, best[1])
    else:
        draw_deck(w, s, None, None, rng)


def policy_call(w: World, s: int) -> str | None:
    if not can_call(w, s):
        return None
    mine = points(w.mine(s))
    return "stop" if mine >= max(points(w.mine(o)) for o in range(len(w.hands)) if o != s) else None


def finish_turn(w: World, s: int, rng: random.Random) -> str | None:
    """Play all duos, then end the turn with the policy's call."""
    while duos := duos_in_hand(w, s):
        play_duo(w, s, duos[0], rng)
    return end_turn(w, s, policy_call(w, s))


def rollout(w: World, rng: random.Random, max_turns: int = 200) -> str:
    for _ in range(max_turns):
        s = w.active
        policy_draw(w, s, rng)
        reason = finish_turn(w, s, rng)
        if reason:
            return reason
    raise RuntimeError("rollout did not end")


def awarded(w: World, reason: str) -> list[int]:
    if reason == "deck_empty":
        return [0] * len(w.hands)
    pts = [points(w.mine(s)) for s in range(len(w.hands))]
    if reason == "stop":
        return pts
    c = w.caller
    assert c is not None
    bon = [bonus(w.mine(s)) for s in range(len(w.hands))]
    won = all(pts[c] >= v for i, v in enumerate(pts) if i != c)
    if won:
        return [pts[i] + bon[i] if i == c else bon[i] for i in range(len(pts))]
    return [bon[i] if i == c else pts[i] for i in range(len(pts))]
