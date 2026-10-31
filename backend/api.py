"""Stateless HTTP API: the client owns the game state and sends it with every request."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.engine.discard_ledger import IllegalAction
from backend.engine.models import Card, GameState
from backend.engine.rules import Action, apply_action, new_game
from backend.solver.ev_calculator import KeepAdvice, Recommendation
from backend.solver.ismcts import advise, keep_search

app = FastAPI(title="SaltEngine")


@app.exception_handler(IllegalAction)
async def _illegal(_: Request, exc: IllegalAction) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


class NewGameRequest(BaseModel):
    names: list[str]
    hero_index: int


class ApplyRequest(BaseModel):
    state: GameState
    action: Action


class StateResponse(BaseModel):
    state: GameState
    recommendation: Recommendation | None


class KeepRequest(BaseModel):
    state: GameState
    first: Card
    second: Card


def _respond(state: GameState) -> StateResponse:
    in_round = state.phase in ("draw", "play_duo")
    return StateResponse(state=state, recommendation=advise(state) if in_round else None)


@app.post("/api/new_game")
def create_game(req: NewGameRequest) -> StateResponse:
    return _respond(new_game(req.names, req.hero_index))


@app.post("/api/apply")
def apply(req: ApplyRequest) -> StateResponse:
    return _respond(apply_action(req.state, req.action))


@app.post("/api/keep")
def keep(req: KeepRequest) -> KeepAdvice:
    return keep_search(req.state, req.first, req.second)
