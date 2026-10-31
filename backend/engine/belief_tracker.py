"""What the hero can infer about hidden cards (the deck and opponents' unseen hand cards).

Prior: every hidden card is a uniform draw from the unseen pool, so card counting alone gives
exact hypergeometric marginals.
Evidence: when an opponent draws blind while card X sits on top of a discard pile, a hand that
already holds X's partner would likely have taken it. Bayes' rule then lowers the chance that
their hand holds X's partner.
"""
from backend.engine.models import CardName, GameState, PlayerState
from backend.engine.rules import unseen_counts

# Assumed behaviour: a player holding a card's partner still passes on that card half the time.
PASS_LIKELIHOOD = 0.5

# The card whose presence in hand "passing on X" is evidence against.
PARTNER: dict[CardName, CardName] = {
    "crab": "crab", "boat": "boat", "fish": "fish", "shark": "swimmer", "swimmer": "shark",
    "shell": "shell", "octopus": "octopus", "penguin": "penguin", "sailor": "sailor",
}

Dist = dict[CardName, float]


def _apply_pass_evidence(prior: Dist, n: int, partner: CardName, times: int) -> Dist:
    """Posterior per-slot distribution after `times` passes on a card pairing with `partner`."""
    q = prior.get(partner, 0.0)
    if n == 0 or q <= 0.0 or q >= 1.0:
        return prior
    p_none = (1 - q) ** n
    lik = PASS_LIKELIHOOD ** times
    post_none = p_none / (p_none + lik * (1 - p_none))
    expected = (1 - post_none) * n * q / (1 - p_none)  # E[#partner | hand holds >= 1] weighted
    q_new = expected / n
    scale = (1 - q_new) / (1 - q)
    return {k: (q_new if k == partner else v * scale) for k, v in prior.items()}


class OpponentBeliefTracker:
    def __init__(self, state: GameState) -> None:
        self.state = state
        self.pool = unseen_counts(state)
        total = sum(self.pool.values())
        self.prior: Dist = {k: v / total for k, v in self.pool.items() if v > 0} if total else {}
        self.slots: dict[str, Dist] = {p.player_id: self._slot_dist(p) for p in state.opponents}
        self.deck = self._deck_dist()

    def _slot_dist(self, p: PlayerState) -> Dist:
        dist = dict(self.prior)
        for name, times in p.passed_on.items():
            if name in PARTNER:
                dist = _apply_pass_evidence(dist, p.unknown_count, PARTNER[name], times)
        return dist

    def _deck_dist(self) -> Dist:
        """Expected count of each card name left in the deck (sums to deck_count)."""
        left = {k: float(v) for k, v in self.pool.items() if v > 0}
        for p in self.state.opponents:
            for k, v in self.slots[p.player_id].items():
                left[k] -= v * p.unknown_count
        # shortcut: evidence can push an estimate below zero when several opponents share it; clamp and renormalise.
        left = {k: max(0.0, v) for k, v in left.items()}
        total = sum(left.values())
        n = self.state.deck_count
        return {k: v * n / total for k, v in left.items() if v > 0} if total else {}

    def expected_hand(self, player_id: str) -> Dist:
        """Expected count of each card name in an opponent's hand (seen + unseen)."""
        p = self.state.player(player_id)
        out: Dist = {k: v * p.unknown_count for k, v in self.slots[player_id].items()}
        for c in p.known_hand:
            out[c.name] = out.get(c.name, 0.0) + 1
        return {k: v for k, v in out.items() if v > 1e-9}

    def summary(self) -> dict[str, dict[str, object]]:
        out: dict[str, dict[str, object]] = {}
        for p in self.state.opponents:
            n = p.unknown_count
            slot = self.slots[p.player_id]
            p_mermaid_unseen = 1 - (1 - slot.get("mermaid", 0.0)) ** n
            out[p.player_id] = {
                "hand_size": p.hand_size,
                "unseen": n,
                "expected_hand": self.expected_hand(p.player_id),
                "p_holds_mermaid": max(p_mermaid_unseen, float(any(c.name == "mermaid" for c in p.known_hand))),
            }
        return out
