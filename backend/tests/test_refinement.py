"""Deterministic contracts for successive batches of live search advice."""
from unittest.mock import Mock

import pytest

from backend.engine.discard_ledger import IllegalAction
from backend.solver import ismcts
from backend.tests.test_rules import _hero_with
from backend.tests.test_scoring import c


@pytest.mark.parametrize("prior_n, expected, count", [(0, 6.0, 100), (200, -2.0, 300)])
def test_refinement_can_reverse_the_new_batch_winner(monkeypatch, prior_n, expected, count):
    state = _hero_with([]).model_copy(update={"phase": "draw"})
    search = Mock(return_value={("draw", "deck"): (0.6, 100), ("draw", "a"): (0.5, 100)})
    monkeypatch.setattr(ismcts, "search", search)
    prior = {"draw:deck": -6.0, "draw:a": 3.0}
    before = state.model_dump()

    rec = ismcts.advise(state, seed=0, prior=prior, prior_n=prior_n)

    assert rec.search == {"draw:deck": expected, "draw:a": 0.0 if prior_n == 0 else 2.0}
    assert rec.search_n == count
    assert rec.search_best == ("draw:deck" if prior_n == 0 else "draw:a")
    assert rec.best_draw == ("deck" if prior_n == 0 else "a")
    search.assert_called_once_with(state, budget_s=ismcts.LIVE_BUDGET_S, seed=0)
    assert prior == {"draw:deck": -6.0, "draw:a": 3.0}
    assert state.model_dump() == before


def test_fresh_advice_reports_margin_and_batch_size(monkeypatch):
    monkeypatch.setattr(ismcts, "search", Mock(return_value={("end", None): (0.55555, 17)}))
    rec = ismcts.advise(_hero_with([]))
    assert rec.search == {"end:none": 3.33}
    assert rec.search_n == 17
    assert rec.search_best == "end:none"


@pytest.mark.parametrize("choice", [None, "stop", "last_chance"])
def test_merged_winner_updates_end_round_advice(monkeypatch, choice):
    state = _hero_with(["shell"] * 5 + ["octopus"] * 2)
    monkeypatch.setattr(ismcts, "search", Mock(return_value={
        ("end", None): (0.5, 10), ("end", "stop"): (0.5, 10), ("end", "last_chance"): (0.5, 10),
    }))
    label = f"end:{choice or 'none'}"
    prior = {"end:none": -3.0, "end:stop": -3.0, "end:last_chance": -3.0}
    prior[label] = 9.0
    rec = ismcts.advise(state, prior=prior, prior_n=10)
    assert rec.search_best == label
    assert rec.end_round.best == (choice or "continue")


def test_merged_winner_moves_duo_to_front(monkeypatch):
    state = _hero_with(["crab", "crab", "fish", "fish"])
    monkeypatch.setattr(ismcts, "search", Mock(return_value={
        ("duo", "crab"): (0.5, 10), ("duo", "fish"): (0.5, 10), ("end", None): (0.5, 10),
    }))
    rec = ismcts.advise(state, prior={"duo:crab": -3, "duo:fish": 9, "end:none": -3}, prior_n=20)
    assert rec.search_best == "duo:fish"
    assert [d.duo for d in rec.duos] == ["fish", "crab"]


@pytest.mark.parametrize("prior", [{}, {"end:none": 0, "extra": 1}, {"draw:deck": 0}])
def test_refinement_rejects_missing_added_or_replaced_options(monkeypatch, prior):
    monkeypatch.setattr(ismcts, "search", Mock(return_value={("end", None): (0.5, 10)}))
    with pytest.raises(IllegalAction, match="decision changed"):
        ismcts.advise(_hero_with([]), prior=prior, prior_n=10)


def test_advice_on_opponent_turn_does_not_search(monkeypatch):
    state = _hero_with([]).model_copy(update={"active_player_id": "p1"})
    search = Mock(side_effect=AssertionError("must not search an opponent's decision"))
    monkeypatch.setattr(ismcts, "search", search)
    rec = ismcts.advise(state, seed=42, prior={"stale": 1}, prior_n=100)
    assert rec.search is None and rec.search_best is None and rec.search_n is None
    search.assert_not_called()


def test_successive_refinements_accumulate_counts_and_round_margins(monkeypatch):
    state = _hero_with([])
    monkeypatch.setattr(ismcts, "search", Mock(side_effect=[
        {("end", None): (0.6, 2)}, {("end", None): (0.4, 3)}, {("end", None): (0.5, 5)},
    ]))
    rec = ismcts.advise(state)
    rec = ismcts.advise(state, prior=rec.search, prior_n=rec.search_n)
    assert rec.search == {"end:none": -1.2} and rec.search_n == 5
    rec = ismcts.advise(state, prior=rec.search, prior_n=rec.search_n)
    assert rec.search == {"end:none": -0.6} and rec.search_n == 10


def test_keep_search_uses_its_budget_and_search_decision(monkeypatch):
    state, first, second = _hero_with([]), c("crab"), c("fish")
    search = Mock(return_value={("keep", 0, "a"): (0.1, 5), ("keep", 1, "b"): (0.9, 5)})
    monkeypatch.setattr(ismcts, "search", search)
    rec = ismcts.keep_search(state, first, second)
    assert (rec.keep_index, rec.discard_pile) == (1, "b")
    search.assert_called_once_with(state, (first, second), budget_s=ismcts.KEEP_BUDGET_S)


@pytest.mark.parametrize("seed", [None, 0, 42])
def test_search_seed_is_reproducible_with_fixed_work(monkeypatch, seed):
    # A zero budget still samples one world per action, avoiding wall-clock dependent counts.
    state = _hero_with(["shell"] * 5 + ["octopus"] * 2)
    original = ismcts.determinize
    samples = []

    def determinize(s, beliefs, rng):
        w = original(s, beliefs, rng)
        samples.append(w.copy())
        return w

    monkeypatch.setattr(ismcts, "determinize", determinize)
    first = ismcts.search(state, seed=seed, budget_s=0)
    first_samples = samples[:]
    samples.clear()
    second = ismcts.search(state, seed=seed, budget_s=0)
    assert first == second
    assert samples == first_samples
    assert all(n == 1 for _, n in first.values())
    if seed is None:
        assert first == ismcts.search(state, seed=state.round_number * 104729 + len(state.log), budget_s=0)
    else:
        samples.clear()
        ismcts.search(state, seed=seed + 1, budget_s=0)
        assert samples != first_samples
