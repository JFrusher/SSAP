import random

from backend.engine.belief_tracker import OpponentBeliefTracker
from backend.engine.models import DECK_SIZE
from backend.solver import fastsim, ismcts
from backend.tests.test_rules import _hero_with


def test_determinized_world_accounts_for_every_card() -> None:
    s = _hero_with(["shell", "crab"])
    w = ismcts.determinize(s, OpponentBeliefTracker(s), random.Random(0))
    n = sum(len(h) for h in w.hands) + sum(len(p) for p in w.played) + len(w.piles["a"]) + len(w.piles["b"]) + len(w.deck)
    assert n == DECK_SIZE


def test_rollouts_always_finish_a_round() -> None:
    s = _hero_with([])
    b = OpponentBeliefTracker(s)
    for seed in range(20):
        w = ismcts.determinize(s, b, random.Random(seed))
        w.active = 0
        reason = fastsim.rollout(w, random.Random(seed))
        assert reason in ("stop", "last_chance", "deck_empty")
        assert len(fastsim.awarded(w, reason)) == 2


def test_search_banks_a_big_lead() -> None:
    s = _hero_with(["shell"] * 5 + ["octopus"] * 2)  # 11 points against an empty-handed opponent
    result = ismcts.search(s, budget_s=0.1)
    choice = ismcts.best(result)
    assert choice[0] == "end" and choice[1] in ("stop", "last_chance")


def test_live_advice_takes_the_decision_from_search() -> None:
    from backend.solver.ismcts import advise

    s = _hero_with(["shell"] * 5 + ["octopus"] * 2)  # big lead, end-round decision
    rec = advise(s)
    assert rec.search and rec.search_best in rec.search
    assert rec.end_round is not None and rec.end_round.best == ("continue" if rec.search_best == "end:none" else rec.search_best.split(":")[1])
    draw = advise(s.model_copy(update={"phase": "draw"}))
    assert draw.search_best == f"draw:{draw.best_draw}"


def test_playout_stop_rule_does_not_peek_at_hidden_hands() -> None:
    w = fastsim.World(hands=[[("shell", "pink")] * 4, [("octopus", "black")] * 5], played=[[("crab", "grey")] * 2, []],
                      piles={"a": [], "b": []}, deck=[], active=0)
    # Player 1 secretly holds 12 points, but only 5 hidden cards (~3.2 points expected) are visible to player 0.
    assert fastsim.points(w.mine(0)) == 7
    assert fastsim.policy_call(w, 0) == "stop"


def test_refine_merges_batches_weighted_by_deals(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import pytest

    from backend.engine.discard_ledger import IllegalAction

    s = _hero_with(["shell"] * 5 + ["octopus"] * 2)
    acts = list(ismcts.search(s, budget_s=0.01))
    # New batch: 100 deals, every action at margin 0 (value 0.5).
    monkeypatch.setattr(ismcts, "search", lambda *a, **k: {a: (0.5, 100) for a in acts})
    prior = {ismcts._label(a): 6.0 for a in acts}
    merged = ismcts.advise(s, seed=2, prior=prior, prior_n=300)
    assert merged.search_n == 400
    assert merged.search == {k: 4.5 for k in prior}  # (6*300 + 0*100) / 400
    with pytest.raises(IllegalAction):
        ismcts.advise(s, seed=3, prior={"draw:deck": 0.0}, prior_n=10)
