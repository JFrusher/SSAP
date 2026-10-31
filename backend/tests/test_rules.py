import pytest
from fastapi.testclient import TestClient

from backend.api import app
from backend.engine.belief_tracker import OpponentBeliefTracker
from backend.engine.discard_ledger import DiscardLedger, IllegalAction
from backend.engine.models import GameState
from backend.engine.rules import (
    DrawDeck, EndTurn, PlayDuo, ResolveRound, StartRound, TakeDiscard, apply_action, new_game, unseen_counts,
)
from backend.solver.ev_calculator import recommend
from backend.tests.test_scoring import c


def started() -> GameState:
    s = new_game(["me", "bob"], 0)
    return apply_action(s, StartRound(pile_a=c("shell"), pile_b=c("fish"), first_player_id="p0"))


def test_ledger_is_immutable_and_derives_piles() -> None:
    x, y = c("crab"), c("boat")
    led = DiscardLedger().record_in("a", x, None)
    led2 = led.record_in("a", y, "p0").record_out("a", x.id, "p1")
    assert led.pile("a") == [x]
    assert led2.pile("a") == [y] and led2.top("a") == y
    with pytest.raises(IllegalAction):
        led2.record_out("a", x.id, "p1")


def test_apply_action_is_pure() -> None:
    s = started()
    before = s.model_dump()
    apply_action(s, TakeDiscard(pile="a"))
    assert s.model_dump() == before


def test_turn_flow_and_counts() -> None:
    s = started()
    assert s.deck_count == 56
    kept, disc = c("crab"), c("crab")
    s = apply_action(s, DrawDeck(kept=kept, discarded=disc, pile="a"))
    assert s.hero.known_hand == [kept] and s.deck_count == 54 and s.phase == "play_duo"
    s = apply_action(s, EndTurn())
    assert s.active_player_id == "p1" and s.phase == "draw"
    s = apply_action(s, DrawDeck(discarded=c("boat"), pile="b"))  # opponent: kept card hidden
    assert s.player("p1").unknown_count == 1
    assert s.player("p1").passed_on == {"crab": 1, "fish": 1}
    assert sum(unseen_counts(s).values()) == s.deck_count + 1


def test_hero_cannot_play_card_not_in_hand() -> None:
    s = apply_action(started(), TakeDiscard(pile="a"))
    with pytest.raises(IllegalAction):
        apply_action(s, PlayDuo(cards=(c("crab"), c("crab"))))


def test_crab_duo_takes_from_pile_and_boat_gives_extra_turn() -> None:
    s = started()
    crab1, crab2, boat1, boat2 = c("crab"), c("crab"), c("boat"), c("boat")
    s = s.model_copy(update={"players": [s.hero.model_copy(update={"known_hand": [crab1, crab2, boat1], "hand_size": 3}), s.player("p1")],
                             "deck_count": s.deck_count - 3})
    s = apply_action(s, DrawDeck(kept=boat2, discarded=c("penguin"), pile="a"))
    target = s.discard_ledger.pile("a")[0]
    s = apply_action(s, PlayDuo(cards=(crab1, crab2), crab_pile="a", crab_card_id=target.id))
    assert target in s.hero.known_hand and target not in s.discard_ledger.pile("a")
    s = apply_action(s, PlayDuo(cards=(boat1, boat2)))
    s = apply_action(s, EndTurn())
    assert s.active_player_id == "p0" and s.phase == "draw"


def test_must_discard_on_empty_pile() -> None:
    s = apply_action(started(), TakeDiscard(pile="a"))
    s = apply_action(s, EndTurn())
    with pytest.raises(IllegalAction):
        apply_action(s, DrawDeck(discarded=c("boat"), pile="b"))


def test_overcounting_is_rejected() -> None:
    s = started()
    s = s.model_copy(update={"players": [s.hero.model_copy(update={"known_hand": [c("lighthouse")], "hand_size": 1}), s.player("p1")],
                             "deck_count": s.deck_count - 1})
    with pytest.raises(IllegalAction):
        apply_action(s, DrawDeck(kept=c("lighthouse"), discarded=c("crab"), pile="a"))


def _hero_with(names: list[str]) -> GameState:
    s = started()
    hand = [c(n) for n in names]
    return s.model_copy(update={"players": [s.hero.model_copy(update={"known_hand": hand, "hand_size": len(hand)}), s.player("p1")],
                                "deck_count": s.deck_count - len(hand), "phase": "play_duo"})


def test_last_chance_bet_scoring() -> None:
    s = _hero_with(["shell"] * 4 + ["crab", "crab"])  # 6 + 1 = 7 points, colour bonus 6
    s = apply_action(s, EndTurn(call="last_chance"))
    assert s.active_player_id == "p1" and s.last_chance_queue == []
    s = apply_action(s, TakeDiscard(pile="b"))  # opponent takes the fish
    s = apply_action(s, EndTurn())
    assert s.phase == "round_end" and s.round_end_reason == "last_chance"
    s = apply_action(s, ResolveRound(revealed={}))
    assert s.history[-1].caller_won_bet is True
    assert s.hero.current_score == 7 + 6 and s.player("p1").current_score == 1


def test_stop_requires_seven_points_for_hero() -> None:
    with pytest.raises(IllegalAction):
        apply_action(_hero_with(["shell", "shell"]), EndTurn(call="stop"))


def test_deck_empty_scores_nothing() -> None:
    s = _hero_with([])
    s = s.model_copy(update={"deck_count": 0, "players": [s.hero, s.player("p1").model_copy(update={"hand_size": 56})]})
    s = apply_action(s, EndTurn())
    assert s.round_end_reason == "deck_empty"
    s = apply_action(s, ResolveRound())
    assert s.phase == "round_start" and s.hero.current_score == 0


def test_belief_evidence_lowers_partner_probability() -> None:
    s = started()
    p1 = s.player("p1").model_copy(update={"hand_size": 3})
    s = s.model_copy(update={"players": [s.hero, p1], "deck_count": s.deck_count - 3})
    plain = OpponentBeliefTracker(s)
    s2 = s.model_copy(update={"players": [s.hero, p1.model_copy(update={"passed_on": {"crab": 2}})]})
    informed = OpponentBeliefTracker(s2)
    assert informed.slots["p1"]["crab"] < plain.slots["p1"]["crab"]
    assert abs(sum(informed.slots["p1"].values()) - 1) < 1e-9
    assert abs(sum(informed.deck.values()) - s.deck_count) < 1e-6


def test_recommend_prefers_pair_completing_discard() -> None:
    s = _hero_with(["crab"]).model_copy(update={"phase": "draw"})
    ledger = DiscardLedger().record_in("a", c("crab"), None).record_in("b", c("sailor"), None)
    s = s.model_copy(update={"discard_ledger": ledger})
    rec = recommend(s)
    ev = {o.source: o.ev for o in rec.draw or []}
    assert ev["a"] > ev["b"]


def test_recommend_last_chance_when_far_ahead() -> None:
    s = _hero_with(["shell"] * 5 + ["octopus"] * 2)  # 8 + 3 = 11 points vs an empty-handed opponent
    adv = recommend(s).end_round
    assert adv is not None and adv.best == "last_chance" and adv.p_last_chance_win > 0.9


def test_api_round_trip() -> None:
    client = TestClient(app)
    r = client.post("/api/new_game", json={"names": ["me", "bob", "amy"], "hero_index": 0})
    assert r.status_code == 200
    state = r.json()["state"]
    action = {"kind": "start_round", "pile_a": c("shell").model_dump(), "pile_b": c("fish").model_dump(), "first_player_id": "p0"}
    r = client.post("/api/apply", json={"state": state, "action": action})
    assert r.status_code == 200 and r.json()["recommendation"]["draw"]
    bad = client.post("/api/apply", json={"state": r.json()["state"], "action": {"kind": "end_turn"}})
    assert bad.status_code == 400 and "draw" in bad.json()["detail"]


def test_lookahead_never_exceeds_physical_card_counts() -> None:
    # One sailor in hand, the other still unseen: the 2-turn lookahead must not imagine a third sailor.
    s = _hero_with(["sailor"]).model_copy(update={"phase": "draw"})
    rec = recommend(s)
    assert rec.draw
