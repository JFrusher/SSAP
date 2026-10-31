"""Expected-value recommendations for the hero.

Value of gaining a card = immediate change in card points + the expected best gain of the
hero's next deck draw (keep best of two) with that card in hand: a two-turn lookahead that
naturally values half-made pairs and set progress.

Colour data for unseen cards does not exist (cards are only coloured when you see them), so a
blind draw's colour adds nothing in the draw EV; the end-of-round simulation samples colours uniformly.
"""
import random
from collections import Counter
from typing import Literal

from pydantic import BaseModel

from backend.engine.belief_tracker import Dist, OpponentBeliefTracker
from backend.engine.models import END_ROUND_MIN_POINTS, NON_WHITE_COLORS, Card, CardName, Color, GameState
from backend.engine.rules import all_cards, color_bonus_counts, counts, score_counts, unseen_counts

SIMULATIONS = 300


class DrawOption(BaseModel):
    source: Literal["deck", "a", "b"]
    card: Card | None
    ev: float


class DuoOption(BaseModel):
    duo: Literal["crab", "boat", "fish", "shark"]
    effect: str
    effect_ev: float
    crab_pile: Literal["a", "b"] | None = None  # best card to take with crabs
    crab_card_id: str | None = None
    steal_from: str | None = None  # best opponent to steal from


class EndRoundAdvice(BaseModel):
    hero_points: int
    stop_margin: float  # expected (hero round score - best opponent round score)
    last_chance_margin: float
    p_last_chance_win: float
    best: Literal["stop", "last_chance", "continue"]


class OpponentView(BaseModel):
    player_id: str
    hand_size: int
    unseen: int
    expected_hand: dict[str, float]
    p_holds_mermaid: float
    est_points: float
    p_can_end: float  # P(card points >= 7)


class KeepAdvice(BaseModel):
    keep_index: int
    values: tuple[float, float]


class Recommendation(BaseModel):
    hero_points: int
    hero_color_bonus: int
    deck: dict[str, float]
    draw: list[DrawOption] | None = None
    best_draw: Literal["deck", "a", "b"] | None = None
    duos: list[DuoOption] | None = None
    end_round: EndRoundAdvice | None = None
    opponents: list[OpponentView]


# ---------------------------------------------------------------- card values


def _gain(names: Counter[CardName], colors: Counter[Color], base: int, name: CardName, color: Color | None) -> int:
    names[name] += 1
    if color:
        colors[color] += 1
    v = score_counts(names, colors) - base
    names[name] -= 1
    if color:
        colors[color] -= 1
    return v


def _best_of_two(values: dict[CardName, float], deck: Dist) -> float:
    """E[max value] of two cards drawn without replacement from the deck."""
    total = sum(deck.values())
    if total < 1:
        return 0.0
    if total < 2:
        return sum(n / total * values[k] for k, n in deck.items())
    acc = weight = 0.0
    for a, na in deck.items():
        for b, nb in deck.items():
            p = na * max(0.0, nb - (a == b))
            acc += p * max(values[a], values[b])
            weight += p
    return acc / weight if weight else 0.0


def _next_draw(names: Counter[CardName], colors: Counter[Color], deck: Dist) -> float:
    base = score_counts(names, colors)
    return _best_of_two({k: float(_gain(names, colors, base, k, None)) for k in deck}, deck)


def card_value(names: Counter[CardName], colors: Counter[Color], deck: Dist, name: CardName, color: Color | None,
               *, from_deck: bool) -> float:
    """Gain now + expected best gain of the next deck draw. A card taken from the deck leaves it first,
    so the lookahead can't imagine more copies of a card than exist."""
    if from_deck:
        deck = {k: v - (k == name) for k, v in deck.items() if v - (k == name) > 0}
    base = score_counts(names, colors)
    g = _gain(names, colors, base, name, color)
    names[name] += 1
    if color:
        colors[color] += 1
    future = _next_draw(names, colors, deck)
    names[name] -= 1
    if color:
        colors[color] -= 1
    return g + future


def _deck_value(names: Counter[CardName], colors: Counter[Color], deck: Dist) -> float:
    return _best_of_two({k: card_value(names, colors, deck, k, None, from_deck=True) for k in deck}, deck)


# ---------------------------------------------------------------- phases


def draw_options(state: GameState, deck: Dist) -> list[DrawOption]:
    names, colors = counts(all_cards(state.hero))
    opts = []
    if state.deck_count > 0:
        opts.append(DrawOption(source="deck", card=None, ev=round(_deck_value(names, colors, deck), 3)))
    for pile in ("a", "b"):
        top = state.discard_ledger.top(pile)  # type: ignore[arg-type]
        if top:
            opts.append(DrawOption(source=pile, card=top, ev=round(card_value(names, colors, deck, top.name, top.color, from_deck=False), 3)))  # type: ignore[arg-type]
    return opts


def keep_advice(state: GameState, first: Card, second: Card) -> KeepAdvice:
    deck = OpponentBeliefTracker(state).deck
    names, colors = counts(all_cards(state.hero))
    v = (card_value(names, colors, deck, first.name, first.color, from_deck=True),
         card_value(names, colors, deck, second.name, second.color, from_deck=True))
    return KeepAdvice(keep_index=0 if v[0] >= v[1] else 1, values=(round(v[0], 3), round(v[1], 3)))


def duo_options(state: GameState, beliefs: OpponentBeliefTracker) -> list[DuoOption]:
    hero = state.hero
    deck = beliefs.deck
    hand = Counter(c.name for c in hero.known_hand)
    names, colors = counts(all_cards(hero))
    out: list[DuoOption] = []
    if hand["crab"] >= 2:
        scored = [(card_value(names, colors, deck, c.name, c.color, from_deck=False), pile, c.id)
                  for pile in ("a", "b") for c in state.discard_ledger.pile(pile)]  # type: ignore[arg-type]
        ev, pile, card_id = max(scored, default=(0.0, None, None))
        out.append(DuoOption(duo="crab", effect="take any card from a discard pile", effect_ev=round(ev, 3),
                             crab_pile=pile, crab_card_id=card_id))  # type: ignore[arg-type]
    if hand["boat"] >= 2:
        ev = max((o.ev for o in draw_options(state, deck)), default=0.0)
        out.append(DuoOption(duo="boat", effect="take another turn", effect_ev=round(ev, 3)))
    if hand["fish"] >= 2:
        total = sum(deck.values())
        ev = sum(n / total * card_value(names, colors, deck, k, None, from_deck=True) for k, n in deck.items()) if total else 0.0
        out.append(DuoOption(duo="fish", effect="draw the top deck card", effect_ev=round(ev, 3)))
    if hand["shark"] >= 1 and hand["swimmer"] >= 1:
        targets: list[tuple[float, str]] = []
        for p in state.opponents:
            if p.hand_size == 0:
                continue
            seen = sum(card_value(names, colors, deck, c.name, c.color, from_deck=False) for c in p.known_hand)
            slot = beliefs.slots[p.player_id]
            unseen = p.unknown_count * sum(w * card_value(names, colors, deck, k, None, from_deck=True) for k, w in slot.items())
            targets.append(((seen + unseen) / p.hand_size, p.player_id))
        best, victim = max(targets, default=(0.0, None))
        out.append(DuoOption(duo="shark", effect="steal a random card from an opponent", effect_ev=round(best, 3), steal_from=victim))
    return out


# ---------------------------------------------------------------- simulation


def _random_color(rng: random.Random, name: CardName) -> Color:
    return "white" if name == "mermaid" else rng.choice(NON_WHITE_COLORS)


def _sample_hidden(state: GameState, beliefs: OpponentBeliefTracker, rng: random.Random) -> tuple[dict[str, tuple[Counter[CardName], Counter[Color]]], Counter[CardName]]:
    """Sample every opponent's full hand and return (hands, remaining deck names)."""
    original = unseen_counts(state)
    remaining = Counter(original)
    hands = {}
    for p in state.opponents:
        names, colors = counts(all_cards(p))
        slot = beliefs.slots[p.player_id]
        for _ in range(p.unknown_count):
            keys = [k for k in remaining if remaining[k] > 0]
            weights = [slot.get(k, 0.0) * remaining[k] / original[k] for k in keys]
            k = rng.choices(keys, weights)[0]
            remaining[k] -= 1
            names[k] += 1
            colors[_random_color(rng, k)] += 1
        hands[p.player_id] = (names, colors)
    return hands, remaining


def _last_turn(names: Counter[CardName], colors: Counter[Color], state: GameState, remaining: Counter[CardName], rng: random.Random) -> int:
    """An opponent's final turn: best of a blind two-card draw or either discard top."""
    base = score_counts(names, colors)
    options: list[tuple[CardName, Color]] = []
    pool = list(remaining.elements())
    for name in rng.sample(pool, min(2, len(pool))):
        options.append((name, _random_color(rng, name)))
    for pile in ("a", "b"):
        top = state.discard_ledger.top(pile)  # type: ignore[arg-type]
        if top:
            options.append((top.name, top.color))
    return base + max((_gain(names, colors, base, n, c) for n, c in options), default=0)


def simulate(state: GameState, beliefs: OpponentBeliefTracker) -> tuple[list[OpponentView], EndRoundAdvice | None]:
    rng = random.Random(state.round_number * 1000 + state.deck_count)
    hero_names, hero_colors = counts(all_cards(state.hero))
    hero_pts = score_counts(hero_names, hero_colors)
    hero_bonus = color_bonus_counts(hero_colors)
    opp_pts: dict[str, list[int]] = {p.player_id: [] for p in state.opponents}
    stop_m = lc_m = lc_wins = 0.0
    for _ in range(SIMULATIONS):
        hands, remaining = _sample_hidden(state, beliefs, rng)
        now = {pid: score_counts(*h) for pid, h in hands.items()}
        for pid, v in now.items():
            opp_pts[pid].append(v)
        stop_m += hero_pts - max(now.values())
        after = {pid: _last_turn(*h, state, remaining, rng) for pid, h in hands.items()}
        bonus = {pid: color_bonus_counts(h[1]) for pid, h in hands.items()}
        if hero_pts >= max(after.values()):
            lc_wins += 1
            lc_m += hero_pts + hero_bonus - max(bonus.values())
        else:
            lc_m += hero_bonus - max(after.values())

    views = []
    summaries = beliefs.summary()
    for p in state.opponents:
        pts = opp_pts[p.player_id]
        summary = summaries[p.player_id]
        views.append(OpponentView(
            player_id=p.player_id, hand_size=p.hand_size, unseen=p.unknown_count,
            expected_hand={k: round(v, 3) for k, v in summary["expected_hand"].items()},  # type: ignore[union-attr]
            p_holds_mermaid=round(float(summary["p_holds_mermaid"]), 3),  # type: ignore[arg-type]
            est_points=round(sum(pts) / len(pts), 2),
            p_can_end=round(sum(v >= END_ROUND_MIN_POINTS for v in pts) / len(pts), 3),
        ))

    can_end = (state.phase == "play_duo" and state.active_player_id == state.hero_id
               and state.last_chance_caller is None and hero_pts >= END_ROUND_MIN_POINTS)
    if not can_end:
        return views, None
    stop_m /= SIMULATIONS
    lc_m /= SIMULATIONS
    best: Literal["stop", "last_chance", "continue"] = "last_chance" if lc_m > stop_m else "stop"
    if max(stop_m, lc_m) < 0:
        best = "continue"
    return views, EndRoundAdvice(hero_points=hero_pts, stop_margin=round(stop_m, 2), last_chance_margin=round(lc_m, 2),
                                 p_last_chance_win=round(lc_wins / SIMULATIONS, 3), best=best)


def recommend(state: GameState) -> Recommendation:
    beliefs = OpponentBeliefTracker(state)
    names, colors = counts(all_cards(state.hero))
    views, end_round = simulate(state, beliefs)
    rec = Recommendation(
        hero_points=score_counts(names, colors), hero_color_bonus=color_bonus_counts(colors),
        deck={k: round(v, 3) for k, v in beliefs.deck.items()}, opponents=views, end_round=end_round,
    )
    if state.active_player_id != state.hero_id:
        return rec
    if state.phase == "draw":
        rec.draw = draw_options(state, beliefs.deck)
        rec.best_draw = max(rec.draw, key=lambda o: o.ev).source if rec.draw else None
    elif state.phase == "play_duo":
        rec.duos = duo_options(state, beliefs)
    return rec

