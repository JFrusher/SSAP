"""Particle-filter beliefs over the full hidden state.

Each particle is a complete guess of every opponent's hand (and therefore the deck's contents).
Particles are built by replaying this round's log: blind draws are sampled, hard facts (a card was
discarded, played or stolen) are enforced, and each opponent choice re-weights the particle by how
likely a softmax-rational player holding that hand was to make it. Steals between two opponents are
exact: each particle samples which card moved, so previously seen cards are never forgotten.
"""
import math
import random
from collections import Counter
from dataclasses import dataclass

from backend.engine.discard_ledger import IllegalAction
from backend.engine.models import DECK_COMPOSITION, NON_WHITE_COLORS, Card, CardName, Color, GameState, LogEntry, Pile
from backend.engine.rules import score_counts

N_PARTICLES = 128
BETA = 1.0  # fixed softmax rationality of opponents (phase 2)
BETA_GRID = (0.0, 1.0, 3.0, 8.0)  # phase 5: each particle draws a beta per opponent; reweighting learns it
# shortcut: a blind deck draw is valued at a constant expected gain; upgrade if opponent fits show it matters.
DECK_OPTION_VALUE = 0.5

HandCard = tuple[CardName, Color, str | None]  # id is None for cards the particle sampled
Dist = dict[CardName, float]


@dataclass
class Particle:
    hands: dict[str, list[HandCard]]
    pool: Counter[CardName]  # exactly the deck's contents in this guess
    beta: dict[str, float]
    logw: float = 0.0

    def copy(self) -> "Particle":
        return Particle({k: list(v) for k, v in self.hands.items()}, Counter(self.pool), dict(self.beta), self.logw)


def _color(rng: random.Random, name: CardName) -> Color:
    return "white" if name == "mermaid" else rng.choice(NON_WHITE_COLORS)


def _score(hand: list[HandCard]) -> int:
    return score_counts(Counter(c[0] for c in hand), Counter(c[1] for c in hand))


def _gain(hand: list[HandCard], base: int, name: CardName, color: Color) -> float:
    """Opponent's value for a card: points now + half the points a second copy would add (set potential).
    The potential term made hand predictions 2.5% better than points alone in arena tests."""
    nxt = hand + [(name, color, None)]
    now = _score(nxt)
    if sum(c[0] == name for c in nxt) + 1 > DECK_COMPOSITION[name]:
        return now - base
    return now - base + 0.5 * max(0, _score(nxt + [(name, color, None)]) - now)


def _log_softmax(values: list[float], beta: float, chosen: int) -> float:
    m = max(beta * v for v in values)
    return beta * values[chosen] - m - math.log(sum(math.exp(beta * v - m) for v in values))


def draw_choice_loglik(hand: list[HandCard], options: list[Card | None], chosen: int, beta: float) -> float:
    """log P(choose option `chosen`); options are pile tops, or None for the blind deck."""
    base = _score(hand)
    values = [DECK_OPTION_VALUE if o is None else _gain(hand, base, o.name, o.color) for o in options]
    return _log_softmax(values, beta, chosen)


def keep_loglik(hand: list[HandCard], kept: HandCard, discarded: Card, beta: float) -> float:
    base = _score(hand)
    return _log_softmax([_gain(hand, base, kept[0], kept[1]), _gain(hand, base, discarded.name, discarded.color)], beta, 0)


def learned_beta(state: GameState) -> "ParticleBelief":
    """Phase 5 belief: opponent rationality is inferred per player from their own choices."""
    return ParticleBelief(state, betas=BETA_GRID)


class ParticleBelief:
    def __init__(self, state: GameState, n: int = N_PARTICLES, betas: tuple[float, ...] = (BETA,)) -> None:
        if not state.log or state.log[0].action.kind != "start_round":
            raise IllegalAction("this round has no move log (it began before an update): start a new round")
        self.state = state
        self.rng = random.Random(state.round_number * 7919 + len(state.log))
        self.opp_ids = [p.player_id for p in state.opponents]
        self.particles = [self._fresh(betas) for _ in range(n)]
        self.piles: dict[Pile, list[Card]] = {"a": [], "b": []}
        for entry in state.log:
            self._step(entry)
            self._resample_if_needed()
        self._check_sizes()
        self.weights = self._normalised()
        self.deck = self._deck()
        self.slots = {pid: self._slot(pid) for pid in self.opp_ids}

    # ------------------------------------------------------------ replay

    def _fresh(self, betas: tuple[float, ...]) -> Particle:
        return Particle({pid: [] for pid in self.opp_ids}, Counter(DECK_COMPOSITION),
                        {pid: self.rng.choice(betas) for pid in self.opp_ids})

    def _sample_name(self, pool: Counter[CardName]) -> CardName | None:
        total = sum(pool.values())
        if total <= 0:
            return None
        r = self.rng.random() * total
        for k, v in pool.items():
            r -= v
            if v > 0 and r < 0:
                return k
        return next(k for k, v in pool.items() if v > 0)

    def _take(self, p: Particle, name: CardName) -> bool:
        """Remove a card of `name` from the particle's deck, moving a sampled copy out of an opponent hand if needed."""
        if p.pool[name] > 0:
            p.pool[name] -= 1
            return True
        holders = [(pid, i) for pid, h in p.hands.items() for i, c in enumerate(h) if c[0] == name and c[2] is None]
        if not holders:
            return False
        pid, i = self.rng.choice(holders)
        repl = self._sample_name(p.pool)
        if repl is None:
            return False
        p.pool[repl] -= 1
        p.hands[pid][i] = (repl, _color(self.rng, repl), None)
        return True

    def _remove(self, p: Particle, pid: str, card: Card) -> bool:
        """Remove a played or stolen card from an opponent's hand, swapping a sampled card for it if needed."""
        hand = p.hands[pid]
        for match in (lambda c: c[2] == card.id, lambda c: c[2] is None and c[0] == card.name):
            i = next((i for i, c in enumerate(hand) if match(c)), None)
            if i is not None:
                hand.pop(i)
                return True
        sampled = [i for i, c in enumerate(hand) if c[2] is None]
        if not sampled:
            return False
        i = self.rng.choice(sampled)
        p.pool[hand[i][0]] += 1  # the guessed card goes back to the deck...
        hand.pop(i)
        return self._take(p, card.name)  # ...and the real one comes out of it

    def _step(self, e: LogEntry) -> None:
        a = e.action
        hero = self.state.hero_id
        tops = [e.top_a, e.top_b]
        if a.kind == "start_round":
            self.piles = {"a": [a.pile_a], "b": [a.pile_b]}
            for p in self.particles:
                ok = self._take(p, a.pile_a.name) and self._take(p, a.pile_b.name)
                p.logw = 0.0 if ok else -math.inf
            return
        for p in self.particles:
            if p.logw == -math.inf:
                continue
            if not self._apply(p, e, hero, tops):
                p.logw = -math.inf
        # public pile bookkeeping, shared by all particles
        if a.kind == "draw_deck" and a.discarded is not None and a.pile is not None:
            self.piles[a.pile].append(a.discarded)
        elif a.kind == "take_discard":
            self.piles[a.pile].pop()
        elif a.kind == "play_duo" and a.crab_pile is not None:
            self.piles[a.crab_pile] = [c for c in self.piles[a.crab_pile] if c.id != a.crab_card_id]

    def _apply(self, p: Particle, e: LogEntry, hero: str, tops: list[Card | None]) -> bool:
        a, actor = e.action, e.actor
        options: list[Card | None] = ([None] if sum(p.pool.values()) > 0 else []) + [t for t in tops if t]
        if a.kind == "draw_deck":
            if actor == hero:
                return all(self._take(p, c.name) for c in (a.kept, a.discarded) if c)
            if a.discarded is not None and not self._take(p, a.discarded.name):
                return False
            name = self._sample_name(p.pool)
            if name is None:
                return False
            p.pool[name] -= 1
            kept: HandCard = (name, _color(self.rng, name), None)
            hand, beta = p.hands[actor], p.beta[actor]
            p.logw += draw_choice_loglik(hand, options, 0, beta)
            if a.discarded is not None:
                p.logw += keep_loglik(hand, kept, a.discarded, beta)
            hand.append(kept)
            return True
        if a.kind == "take_discard":
            top = tops[0 if a.pile == "a" else 1]
            assert top is not None
            if actor != hero:
                hand = p.hands[actor]
                p.logw += draw_choice_loglik(hand, options, options.index(top), p.beta[actor])
                hand.append((top.name, top.color, top.id))
            return True
        if a.kind != "play_duo":
            return True
        if actor != hero and not all(self._remove(p, actor, c) for c in a.cards):
            return False
        if a.crab_pile is not None:
            card = next(c for c in self.piles[a.crab_pile] if c.id == a.crab_card_id)
            if actor != hero:
                p.hands[actor].append((card.name, card.color, card.id))
        if a.cards[0].name == "fish" and sum(p.pool.values()) > 0:
            if actor == hero:
                return a.fish_card is None or self._take(p, a.fish_card.name)
            name = self._sample_name(p.pool)
            assert name is not None
            p.pool[name] -= 1
            p.hands[actor].append((name, _color(self.rng, name), None))
        if a.steal_from is not None:
            victim = a.steal_from
            if victim == hero:
                assert a.stolen_card is not None
                p.hands[actor].append((a.stolen_card.name, a.stolen_card.color, a.stolen_card.id))
            elif actor == hero:
                assert a.stolen_card is not None
                return self._remove(p, victim, a.stolen_card)
            else:
                vh = p.hands[victim]
                if not vh:
                    return False
                p.hands[actor].append(vh.pop(self.rng.randrange(len(vh))))  # exact: a uniformly random card moves
        return True

    def _normalised(self) -> list[float]:
        m = max(p.logw for p in self.particles)
        if m == -math.inf:
            raise IllegalAction("the recorded moves contradict each other: check the last few entries")
        w = [math.exp(p.logw - m) for p in self.particles]
        s = sum(w)
        return [x / s for x in w]

    def _resample_if_needed(self) -> None:
        w = self._normalised()
        ess = 1.0 / sum(x * x for x in w)
        if ess >= len(w) / 2:
            return
        n = len(w)
        step, u, c, i, out = 1.0 / n, self.rng.random() / n, w[0], 0, []
        for _ in range(n):  # systematic resampling
            while u > c:
                i += 1
                c += w[i]
            q = self.particles[i].copy()
            q.logw = 0.0
            out.append(q)
            u += step
        self.particles = out

    def _check_sizes(self) -> None:
        for pid in self.opp_ids:
            size = self.state.player(pid).hand_size
            for p in self.particles:
                if p.logw > -math.inf and len(p.hands[pid]) != size:
                    raise AssertionError(f"particle hand for {pid} has {len(p.hands[pid])} cards, state says {size}")

    # ------------------------------------------------------------ outputs (same interface as OpponentBeliefTracker)

    def _deck(self) -> Dist:
        out: Counter[CardName] = Counter()
        for w, p in zip(self.weights, self.particles):
            for k, v in p.pool.items():
                out[k] += w * v  # type: ignore[assignment]
        return {k: v for k, v in out.items() if v > 1e-9}

    def _unseen_part(self, p: Particle, pid: str) -> list[HandCard]:
        known = {c.id for c in self.state.player(pid).known_hand}
        return [c for c in p.hands[pid] if c[2] not in known]

    def _slot(self, pid: str) -> Dist:
        n = self.state.player(pid).unknown_count
        if n == 0:
            return {}
        out: Counter[CardName] = Counter()
        for w, p in zip(self.weights, self.particles):
            for c in self._unseen_part(p, pid):
                out[c[0]] += w / n  # type: ignore[assignment]
        return dict(out)

    def expected_hand(self, pid: str) -> Dist:
        out: Counter[CardName] = Counter()
        for w, p in zip(self.weights, self.particles):
            for c in p.hands[pid]:
                out[c[0]] += w  # type: ignore[assignment]
        return {k: v for k, v in out.items() if v > 1e-9}

    def summary(self) -> dict[str, dict[str, object]]:
        return {pid: {
            "hand_size": self.state.player(pid).hand_size,
            "unseen": self.state.player(pid).unknown_count,
            "expected_hand": self.expected_hand(pid),
            "p_holds_mermaid": sum(w for w, p in zip(self.weights, self.particles) if any(c[0] == "mermaid" for c in p.hands[pid])),
        } for pid in self.opp_ids}

    def beta_posterior(self, pid: str) -> dict[float, float]:
        out: Counter[float] = Counter()
        for w, p in zip(self.weights, self.particles):
            out[p.beta[pid]] += w  # type: ignore[assignment]
        return dict(out)

    def sample_hidden(self, rng: random.Random) -> tuple[dict[str, tuple[Counter[CardName], Counter[Color]]], Counter[CardName]]:
        """One joint guess: every opponent's full hand and the deck's contents."""
        p = rng.choices(self.particles, self.weights)[0]
        hands = {}
        for pid in self.opp_ids:
            played = self.state.player(pid).played_duos
            cards = p.hands[pid]
            hands[pid] = (Counter([c[0] for c in cards] + [c.name for c in played]),
                          Counter([c[1] for c in cards] + [c.color for c in played]))
        return hands, Counter(p.pool)
