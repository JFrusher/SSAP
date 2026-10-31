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
