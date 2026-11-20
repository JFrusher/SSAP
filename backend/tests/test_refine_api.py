"""HTTP contract for stateless refinement; simulations are tested separately."""
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend import api
from backend.engine.discard_ledger import IllegalAction
from backend.solver.ev_calculator import Recommendation
from backend.tests.test_rules import _hero_with


@pytest.fixture
def payload():
    return {"state": _hero_with([]).model_dump(mode="json"), "search": {"end:none": -1.25},
            "search_n": 23, "seed": 0}


def test_refine_forwards_prior_and_serializes_recommendation(monkeypatch, payload):
    rec = Recommendation(hero_points=0, hero_color_bonus=0, deck={}, opponents=[],
                         search={"end:none": 2.5}, search_best="end:none", search_n=50)
    advise = Mock(return_value=rec)
    monkeypatch.setattr(api, "advise", advise)
    with TestClient(api.app) as client:
        response = client.post("/api/refine", json=payload)
    assert response.status_code == 200
    assert response.json() == rec.model_dump(mode="json")
    state = advise.call_args.args[0]
    assert state.model_dump(mode="json") == payload["state"]
    assert advise.call_args.kwargs == {"seed": 0, "prior": payload["search"], "prior_n": 23}
    advise.assert_called_once()


def test_refine_returns_bad_request_for_changed_decision(monkeypatch, payload):
    monkeypatch.setattr(api, "advise", Mock(side_effect=IllegalAction("decision changed")))
    with TestClient(api.app) as client:
        response = client.post("/api/refine", json=payload)
    assert response.status_code == 400
    assert response.json() == {"detail": "decision changed"}


@pytest.mark.parametrize("field", ["state", "search", "search_n", "seed"])
def test_refine_requires_all_request_fields(monkeypatch, payload, field):
    advise = Mock()
    monkeypatch.setattr(api, "advise", advise)
    del payload[field]
    with TestClient(api.app) as client:
        response = client.post("/api/refine", json=payload)
    assert response.status_code == 422
    advise.assert_not_called()
