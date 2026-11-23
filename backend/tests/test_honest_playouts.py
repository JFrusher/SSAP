"""Opponent estimates must depend only on public information."""
import pytest

from backend.solver import fastsim as fs


def world():
    return fs.World(hands=[[("shell", "pink")] * 4], played=[[("crab", "grey")] * 2],
                    piles={"a": [], "b": []}, deck=[], active=0)


@pytest.mark.parametrize("hidden_count, expected", [(0, 1.0), (1, 1.64), (5, 4.2)])
def test_estimate_counts_public_duos_and_hidden_cards(hidden_count, expected):
    w = world()
    w.hands.append([("octopus", "black")] * hidden_count)
    w.public.append([])
    w.played.append([("crab", "grey")] * 2)
    assert fs.estimate_points(w, 1) == pytest.approx(expected)


def test_hidden_card_identity_and_color_do_not_change_estimate_or_call():
    w = world()
    w.hands.append([("shell", "pink")] * 5)
    w.public.append([])
    w.played.append([])
    estimate, call = fs.estimate_points(w, 1), fs.policy_call(w, 0)
    w.hands[1] = [("octopus", "black")] * 5
    assert fs.estimate_points(w, 1) == estimate
    assert fs.policy_call(w, 0) == call == "stop"


@pytest.mark.parametrize("opponent_shells, expected", [(4, "stop"), (5, None)])
def test_call_compares_against_strongest_of_multiple_opponents(opponent_shells, expected):
    w = world()  # seven points
    w.hands.extend([[], []])
    w.public.extend([[], []])
    w.played.extend([[], [("shell", "pink")] * opponent_shells])  # six or eight public points
    assert fs.policy_call(w, 0) == expected


def test_call_accepts_a_tied_public_estimate():
    w = world()
    w.hands.append([])
    w.public.append([])
    w.played.append(w.mine(0))
    assert fs.estimate_points(w, 1) == 7
    assert fs.policy_call(w, 0) == "stop"


@pytest.mark.parametrize("caller, shells", [(None, 3), (1, 4)])
def test_call_requires_seven_points_and_no_existing_caller(caller, shells):
    w = world()
    w.hands[0] = [("shell", "pink")] * shells
    w.hands.append([])
    w.public.append([])
    w.played.append([])
    w.caller = caller
    assert fs.policy_call(w, 0) is None
