import pytest

from backend.engine.discard_ledger import IllegalAction
from backend.engine.models import GameState
from backend.engine.particle_belief import ParticleBelief
from backend.engine.rules import DrawDeck, EndTurn, PlayDuo, StartRound, TakeDiscard, apply_action, new_game
from backend.tests.test_scoring import c


def _three_player_steal() -> tuple[GameState, str]:
    """p1 takes a known crab from the discard; later p2 steals a random card from p1 (hero p0 sees neither)."""
    s = new_game(["me", "p1", "p2"], 0)
    crab = c("crab")
    s = apply_action(s, StartRound(pile_a=crab, pile_b=c("shell"), first_player_id="p1"))
    s = apply_action(s, TakeDiscard(pile="a"))  # p1 takes the crab
    s = apply_action(s, EndTurn())
    for _ in range(2):  # p2, p0, p1 draw blind
        s = apply_action(s, DrawDeck(discarded=c("boat"), pile="a"))  # p2
        s = apply_action(s, EndTurn())
        s = apply_action(s, DrawDeck(kept=c("octopus"), discarded=c("boat"), pile="a"))  # p0 (hero)
        s = apply_action(s, EndTurn())
        s = apply_action(s, DrawDeck(discarded=c("fish"), pile="b"))  # p1
        s = apply_action(s, EndTurn())
    s = apply_action(s, DrawDeck(discarded=c("boat"), pile="a"))  # p2 now holds 3 unseen cards
    s = apply_action(s, PlayDuo(cards=(c("shark"), c("swimmer")), steal_from="p1"))
    return s, crab.id


def test_opponent_to_opponent_steal_keeps_the_seen_card() -> None:
    s, crab_id = _three_player_steal()
    assert s.player("p1").known_hand == []  # the rules engine has to forget which card moved...
    b = ParticleBelief(s, n=400)
    with_p1 = sum(w for w, p in zip(b.weights, b.particles) if any(card[2] == crab_id for card in p.hands["p1"]))
    with_p2 = sum(w for w, p in zip(b.weights, b.particles) if any(card[2] == crab_id for card in p.hands["p2"]))
    assert with_p1 + with_p2 == pytest.approx(1.0)  # ...the particles never lose it
    assert 0.25 < with_p2 < 0.6  # p1 held 3 cards, so ~1/3 chance it was the stolen one


def test_particles_match_state_counts() -> None:
    s, _ = _three_player_steal()
    b = ParticleBelief(s)
    assert sum(b.deck.values()) == pytest.approx(s.deck_count)
    for pid in ("p1", "p2"):
        assert sum(b.expected_hand(pid).values()) == pytest.approx(s.player(pid).hand_size)
        assert sum(b.slots[pid].values()) == pytest.approx(1.0)


def test_state_without_round_log_fails_fast() -> None:
    s, _ = _three_player_steal()
    with pytest.raises(IllegalAction):
        ParticleBelief(s.model_copy(update={"log": []}))


def _mid_round_posteriors(opponent: str) -> list[dict[float, float]]:
    import random

    from backend.arena import sim
    from backend.arena.bots import GreedyBot, RandomBot
    from backend.engine.particle_belief import learned_beta

    out: list[dict[float, float]] = []
    orig = sim.Table.apply_all

    def spy(self: sim.Table, public, private=None) -> None:  # type: ignore[no-untyped-def]
        orig(self, public, private)
        v = self.views[0]
        if v.phase == "draw" and v.active_player_id == v.hero_id and len(v.log) > 25:
            out.append(learned_beta(v).beta_posterior("p1"))

    sim.Table.apply_all = spy  # type: ignore[method-assign]
    try:
        for seed in range(3):
            sim.play_game([GreedyBot(), RandomBot() if opponent == "random" else GreedyBot()], random.Random(seed))
    finally:
        sim.Table.apply_all = orig  # type: ignore[method-assign]
    return out


def test_learned_beta_tells_a_random_opponent_from_a_greedy_one() -> None:
    def mean_beta(posts: list[dict[float, float]]) -> float:
        return sum(sum(b * w for b, w in post.items()) for post in posts) / len(posts)

    assert mean_beta(_mid_round_posteriors("random")) < mean_beta(_mid_round_posteriors("greedy"))
