# SaltEngine: Sea Salt & Paper assistant

A phone-first web app that tracks a live game of Sea Salt & Paper (base game, 58 cards),
counts cards, infers opponents' hidden hands and recommends draws, duo plays and
Stop / Last Chance calls.

## How it works

- **Stateless engine.** The game state lives in your phone's browser (localStorage). Every action is sent with the
  full state to `POST /api/apply`, which returns the new state and fresh advice. This keeps
  `apply_action(state, action) -> new_state` pure and lets it run as a Vercel serverless function.
- **Card counting.** The discard piles are derived from an immutable ledger (`discard_ledger.py`). Every transition
  checks that the recorded cards are consistent with the 58-card deck and rejects anything that isn't.
- **Beliefs** (`belief_tracker.py`). Hidden cards are uniform draws from the unseen pool (exact hypergeometric
  marginals). One Bayesian update on top: an opponent who draws blind past a discard card is less likely to hold its
  partner (assumed likelihood 0.5).
- **EV** (`ev_calculator.py`). A card's value is the immediate change in points plus the expected best gain of your next deck
  draw. Duo effects are valued the same way. Stop vs Last Chance runs 300 Monte Carlo samples of opponents' hands
  and their final turns.

## Layout

```
backend/engine   models, rules (scoring + transitions), discard_ledger, belief_tracker
backend/solver   ev_calculator
backend/api.py   FastAPI (stateless)
api/index.py     Vercel entrypoint
frontend/        React + TypeScript + Tailwind (Vite)
```

## Run locally

```
pip install -r requirements.txt fastapi uvicorn pytest httpx
python -m pytest
python -m uvicorn backend.api:app --port 8000
cd frontend && npm install && npm run dev   # proxies /api to :8000
```

## Known limits

- You tap each card's colour when you record it. No per-card colour list is built in, so the colours of unseen cards
  are unknown: draw EV ignores them, and the end-of-round simulation assumes uniform colours.
- Base game only; the Extra Salt expansion is not modelled. The 4-mermaid instant win is only checked when a round is scored.
- If one opponent steals from another, the victim's seen cards become "unseen" again (it can't be known which one moved).
- `solver/mcts.py` (optional lookahead) is not built.
