"""Information-set Monte Carlo search for the hero's current decision.

Each iteration samples a full hidden world consistent with the hero's information (a determinization
from the belief model), applies one candidate root action, and plays the round out with the fast rollout
policy. Every root action is evaluated on the same worlds (common random numbers) within a time budget. Search depth is the root
decision only; deeper choices are made by the rollout policy.
"""
import json
import math
import random
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from backend.engine.models import Card, GameState
from backend.solver import fastsim as fs
from backend.solver.ev_calculator import BELIEFS, BeliefFactory, KeepAdvice, Recommendation, keep_advice, recommend

BUDGET_S = 0.15
RootAction = tuple[Any, ...]
# Maps (world, round-end reason, hero seat, state) -> value in [0, 1].
Evaluator = Callable[[fs.World, str, int, GameState], float]


def margin_value(w: fs.World, reason: str, hero: int, state: GameState) -> float:
    got = fs.awarded(w, reason)
    margin = got[hero] - max(v for i, v in enumerate(got) if i != hero)
    return min(1.0, max(0.0, (margin + 30) / 60))


def features(mine: int, best_other: int, target: int) -> list[float]:
    """Scores as fractions of the target: bias, my progress, opponent progress, interaction."""
    m, o = mine / target, best_other / target
    return [1.0, m, o, m * o]


_WIN_MODEL: dict[str, dict[str, Any]] = json.loads((Path(__file__).parent / "win_model.json").read_text())


def win_prob(mine: int, best_other: int, players: int) -> float:
    """P(win the game) at a round start, from self-play (backend/arena/value_table.py)."""
    m = _WIN_MODEL[str(players)]
    z = sum(a * b for a, b in zip(m["weights"], features(mine, best_other, m["target"])))
    return 1 / (1 + math.exp(-z))


def win_value(w: fs.World, reason: str, hero: int, state: GameState) -> float:
    """Phase 4: value a finished round by the hero's chance of winning the whole game."""
    got = fs.awarded(w, reason)
    totals = [p.current_score + got[i] for i, p in enumerate(state.players)]
    mermaids = [i for i in range(len(totals)) if sum(c[0] == "mermaid" for c in w.mine(i)) == 4]
    if mermaids:
        return float(mermaids[0] == hero)
    top = max(totals)
    if top >= state.target_score:
        leaders = [i for i, t in enumerate(totals) if t == top]
        return 1 / len(leaders) if hero in leaders else 0.0  # shortcut: ties split evenly, rulebook tiebreak not modelled
    return win_prob(totals[hero], max(t for i, t in enumerate(totals) if i != hero), len(totals))


def determinize(state: GameState, beliefs: Any, rng: random.Random) -> fs.World:
    hands_counts, pool = beliefs.sample_hidden(rng)
    hands, played = [], []
    for p in state.players:
        known = [(c.name, c.color) for c in p.known_hand]
        played.append([(c.name, c.color) for c in p.played_duos])
        if p.player_id == state.hero_id:
            hands.append(known)
            continue
        unseen = Counter(hands_counts[p.player_id][0])
        unseen.subtract(c.name for c in p.played_duos)
        unseen.subtract(c[0] for c in known)
        assert all(v >= 0 for v in unseen.values()), "belief sample contradicts a seen card"
        hands.append(known + [(n, fs.random_color(rng, n)) for n in unseen.elements()])
    deck = [(n, fs.random_color(rng, n)) for n in pool.elements()]
    rng.shuffle(deck)
    seat = {p.player_id: i for i, p in enumerate(state.players)}
    piles = {k: [(c.name, c.color) for c in state.discard_ledger.pile(k)] for k in ("a", "b")}  # type: ignore[arg-type]
    return fs.World(hands, played, piles, deck, seat[state.active_player_id],
                    seat[state.last_chance_caller] if state.last_chance_caller else None,
                    [seat[q] for q in state.last_chance_queue], state.extra_turn_pending)


def _extract(w: fs.World, card: Card, rng: random.Random) -> None:
    """Remove a card the hero has just seen from the hidden part of a sampled world."""
    i = next((i for i, c in enumerate(w.deck) if c[0] == card.name), None)
    if i is not None:
        w.deck.pop(i)
        return
    for h in rng.sample(range(len(w.hands)), len(w.hands)):
        j = next((j for j, c in enumerate(w.hands[h]) if c[0] == card.name), None)
        if j is not None and w.deck:
            w.hands[h][j] = w.deck.pop()  # that opponent gets a deck card in its place
            return
    raise AssertionError(f"{card.name} cannot be in the hidden cards")


def root_actions(state: GameState, w: fs.World, hero: int, drawn: tuple[Card, Card] | None) -> list[RootAction]:
    if drawn is not None:
        empty = [p for p in ("a", "b") if not w.piles[p]]
        return [("keep", i, p) for i in (0, 1) for p in (empty or ["a", "b"])]
    if state.phase == "draw":
        return ([("draw", "deck")] if w.deck else []) + [("draw", p) for p in ("a", "b") if w.piles[p]]
    acts: list[RootAction] = [("duo", d) for d in fs.duos_in_hand(w, hero)] + [("end", None)]
    if fs.can_call(w, hero):
        acts += [("end", "stop"), ("end", "last_chance")]
    return acts


def _play(w: fs.World, a: RootAction, hero: int, drawn: tuple[Card, Card] | None, rng: random.Random) -> str:
    if a[0] == "keep":
        assert drawn is not None
        cards = [(c.name, c.color) for c in drawn]
        w.hands[hero].append(cards[a[1]])
        w.piles[a[2]].append(cards[1 - a[1]])
        reason = fs.finish_turn(w, hero, rng)
    elif a[0] == "draw":
        if a[1] == "deck":
            fs.draw_deck(w, hero, None, None, rng)
        else:
            fs.draw_pile(w, hero, a[1])
        reason = fs.finish_turn(w, hero, rng)
    elif a[0] == "duo":
        fs.play_duo(w, hero, a[1], rng)
        reason = fs.finish_turn(w, hero, rng)
    else:
        reason = fs.end_turn(w, hero, a[1])
    return reason or fs.rollout(w, rng)


def search(state: GameState, drawn: tuple[Card, Card] | None = None, budget_s: float = BUDGET_S,
           beliefs: BeliefFactory | None = None, evaluate: Evaluator = margin_value) -> dict[RootAction, tuple[float, int]]:
    """Returns {root action: (mean value, visits)} for the hero's current decision."""
    rng = random.Random(state.round_number * 104729 + len(state.log))
    b = (beliefs or BELIEFS)(state)
    hero = [p.player_id for p in state.players].index(state.hero_id)

    def world() -> fs.World:
        w = determinize(state, b, rng)
        for c in drawn or ():
            _extract(w, c, rng)
        return w

    actions = root_actions(state, world(), hero, drawn)
    total = {a: 0.0 for a in actions}
    deadline = time.perf_counter() + budget_s
    n = 0
    # Common random numbers: every action is played on the same sampled world with the same rollout seed,
    # so action comparisons are paired and the noise of the deal cancels out.
    while n == 0 or time.perf_counter() < deadline:
        w0, seed = world(), rng.random()
        for a in actions:
            w = w0.copy()
            r = random.Random(seed)
            total[a] += evaluate(w, _play(w, a, hero, drawn, r), hero, state)
        n += 1
    return {a: (total[a] / n, n) for a in actions}


def best(result: dict[RootAction, tuple[float, int]]) -> RootAction:
    return max(result, key=lambda a: (result[a][1], result[a][0]))


# ------------------------------------------------------------ live advice (arena: search beat greedy 75.7% [70.5, 80.2])

def _label(a: RootAction) -> str:
    return ":".join("none" if x is None else str(x) for x in a)


def _margin(v: float) -> float:
    return round(v * 60 - 30, 2)  # undo margin_value's normalisation: expected round margin vs best opponent


def advise(state: GameState) -> Recommendation:
    """Greedy recommendation (for the numbers shown) with the hero's decision taken from search."""
    rec = recommend(state)
    if state.active_player_id != state.hero_id:
        return rec
    result = search(state)
    choice = best(result)
    rec.search = {_label(a): _margin(v) for a, (v, _) in result.items()}
    rec.search_best = _label(choice)
    if choice[0] == "draw":
        rec.best_draw = choice[1]
    elif choice[0] == "duo" and rec.duos:
        rec.duos.sort(key=lambda d: d.duo != choice[1])  # the searched duo first
    elif choice[0] == "end" and rec.end_round is not None:
        rec.end_round.best = choice[1] or "continue"
    return rec


def keep_search(state: GameState, first: Card, second: Card) -> KeepAdvice:
    """Which drawn card to keep and where to discard the other, decided by search."""
    advice = keep_advice(state, first, second)
    keep, pile = best(search(state, (first, second)))[1:]
    return advice.model_copy(update={"keep_index": keep, "discard_pile": pile})
