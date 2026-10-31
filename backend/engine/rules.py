"""Scoring and pure state transitions: apply_action(state, action) -> new state."""
from collections import Counter
from collections.abc import Iterable

from backend.engine.discard_ledger import DiscardLedger, IllegalAction
from backend.engine.models import (  # noqa: F401  (action classes re-exported for callers)
    Action,
    DrawDeck,
    EndTurn,
    LogEntry,
    PlayDuo,
    ResolveRound,
    StartRound,
    TakeDiscard,
    DECK_COMPOSITION,
    DECK_SIZE,
    END_ROUND_MIN_POINTS,
    NON_WHITE_COLORS,
    TARGET_SCORE,
    Card,
    CardName,
    Color,
    GameState,
    PlayerState,
    RoundResult,
)

# ---------------------------------------------------------------- scoring

SHELL_POINTS = [0, 0, 2, 4, 6, 8, 10]
OCTOPUS_POINTS = [0, 0, 3, 6, 9, 12]
PENGUIN_POINTS = [0, 1, 3, 5]
SAILOR_POINTS = [0, 0, 5]


def score_counts(names: Counter[CardName], colors: Counter[Color]) -> int:
    """Card points for a player's cards (hand + played duos), given name and colour counts."""
    pts = names["crab"] // 2 + names["boat"] // 2 + names["fish"] // 2 + min(names["shark"], names["swimmer"])
    pts += SHELL_POINTS[names["shell"]] + OCTOPUS_POINTS[names["octopus"]]
    pts += PENGUIN_POINTS[names["penguin"]] + SAILOR_POINTS[names["sailor"]]
    pts += names["lighthouse"] * names["boat"] + names["shoal"] * names["fish"]
    pts += names["colony"] * 2 * names["penguin"] + names["captain"] * 3 * names["sailor"]
    if names["mermaid"]:
        ranked = sorted((colors[c] for c in NON_WHITE_COLORS), reverse=True)
        pts += sum(ranked[: names["mermaid"]])
    return pts


def color_bonus_counts(colors: Counter[Color]) -> int:
    """1 point per card of the player's most common colour (mermaids/white excluded)."""
    return max(colors[c] for c in NON_WHITE_COLORS)


def counts(cards: Iterable[Card]) -> tuple[Counter[CardName], Counter[Color]]:
    cards = list(cards)
    return Counter(c.name for c in cards), Counter(c.color for c in cards)


def card_points(cards: Iterable[Card]) -> int:
    return score_counts(*counts(cards))


def color_bonus(cards: Iterable[Card]) -> int:
    return color_bonus_counts(counts(cards)[1])


def all_cards(p: PlayerState) -> list[Card]:
    return p.known_hand + p.played_duos


# ---------------------------------------------------------------- helpers


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise IllegalAction(msg)


def _replace_player(state: GameState, p: PlayerState) -> GameState:
    return state.model_copy(update={"players": [p if q.player_id == p.player_id else q for q in state.players]})


def _add_card(p: PlayerState, card: Card | None) -> PlayerState:
    """Add a card to a hand; None means a card the hero can't see."""
    known = p.known_hand + [card] if card else p.known_hand
    return p.model_copy(update={"hand_size": p.hand_size + 1, "known_hand": known})


def _remove_card(p: PlayerState, card: Card | None, is_hero: bool) -> PlayerState:
    """Remove a card from a hand. A card not in known_hand came from the opponent's unseen cards."""
    if card and any(c.id == card.id for c in p.known_hand):
        return p.model_copy(update={"hand_size": p.hand_size - 1, "known_hand": [c for c in p.known_hand if c.id != card.id]})
    _require(not is_hero, f"{card.name if card else 'card'} is not in your hand")
    _require(p.unknown_count > 0, f"{p.name} has no unseen cards left")
    return p.model_copy(update={"hand_size": p.hand_size - 1})


def _next_player(state: GameState, player_id: str) -> str:
    ids = [p.player_id for p in state.players]
    return ids[(ids.index(player_id) + 1) % len(ids)]


def unseen_counts(state: GameState) -> Counter[CardName]:
    """Cards the hero has not seen this round: the deck plus opponents' unseen hand cards."""
    seen = [c for p in state.players for c in all_cards(p)]
    seen += state.discard_ledger.pile("a") + state.discard_ledger.pile("b")
    pool = Counter(DECK_COMPOSITION)
    pool.subtract(c.name for c in seen)
    return pool


def assert_consistent(state: GameState) -> None:
    """Fail fast if the tracked cards contradict the 58-card deck."""
    if state.phase == "round_start":
        return
    pool = unseen_counts(state)
    over = [n for n, k in pool.items() if k < 0]
    _require(not over, f"more {', '.join(over)} cards recorded than exist in the deck")
    hidden = state.deck_count + sum(p.unknown_count for p in state.opponents)
    _require(sum(pool.values()) == hidden, f"card count mismatch: {sum(pool.values())} unseen vs {hidden} hidden")
    _require(state.hero.unknown_count == 0, "hero hand must be fully known")


# ---------------------------------------------------------------- transitions


def new_game(names: list[str], hero_index: int) -> GameState:
    _require(2 <= len(names) <= 4, "Sea Salt & Paper is for 2-4 players")
    _require(0 <= hero_index < len(names), "hero index out of range")
    players = [
        PlayerState(player_id=f"p{i}", name=n, is_human=i == hero_index, hand_size=0)
        for i, n in enumerate(names)
    ]
    return GameState(
        players=players,
        hero_id=f"p{hero_index}",
        active_player_id="p0",
        deck_count=DECK_SIZE,
        discard_ledger=DiscardLedger(),
        phase="round_start",
        target_score=TARGET_SCORE[len(names)],
    )


def _start_round(state: GameState, a: StartRound) -> GameState:
    _require(state.phase == "round_start", "a round is already in progress")
    state.player(a.first_player_id)
    players = [p.model_copy(update={"hand_size": 0, "known_hand": [], "played_duos": [], "passed_on": {}}) for p in state.players]
    ledger = DiscardLedger().record_in("a", a.pile_a, None).record_in("b", a.pile_b, None)
    return state.model_copy(update={
        "players": players, "discard_ledger": ledger, "deck_count": DECK_SIZE - 2,
        "active_player_id": a.first_player_id, "phase": "draw", "round_number": state.round_number + 1,
        "extra_turn_pending": False, "last_chance_caller": None, "last_chance_queue": [], "round_end_reason": None,
    })


def _draw_deck(state: GameState, a: DrawDeck) -> GameState:
    _require(state.phase == "draw", "not in the draw phase")
    _require(state.deck_count > 0, "the deck is empty")
    p = state.player(state.active_player_id)
    is_hero = p.player_id == state.hero_id
    _require((a.kept is not None) == is_hero, "record the kept card for yourself only (opponents' kept card is hidden)")
    ledger = state.discard_ledger
    drawn = min(2, state.deck_count)
    if drawn == 2:
        _require(a.discarded is not None and a.pile is not None, "choose the discarded card and its pile")
        empty = [x for x in ("a", "b") if ledger.top(x) is None]  # type: ignore[arg-type]
        _require(not empty or a.pile in empty, f"pile {empty[0] if empty else ''} is empty: you must discard there")
    else:
        _require(a.discarded is None, "only one card was left: nothing to discard")
    if not is_hero:
        passed = dict(p.passed_on)
        for pile in ("a", "b"):
            top = ledger.top(pile)  # type: ignore[arg-type]
            if top:
                passed[top.name] = passed.get(top.name, 0) + 1
        p = p.model_copy(update={"passed_on": passed})
    if a.discarded is not None and a.pile is not None:
        ledger = ledger.record_in(a.pile, a.discarded, p.player_id)
    state = state.model_copy(update={"deck_count": state.deck_count - drawn, "discard_ledger": ledger, "phase": "play_duo"})
    return _replace_player(state, _add_card(p, a.kept))


def _take_discard(state: GameState, a: TakeDiscard) -> GameState:
    _require(state.phase == "draw", "not in the draw phase")
    top = state.discard_ledger.top(a.pile)
    _require(top is not None, f"discard pile {a.pile} is empty")
    assert top is not None
    p = state.player(state.active_player_id)
    state = state.model_copy(update={"discard_ledger": state.discard_ledger.record_out(a.pile, top.id, p.player_id), "phase": "play_duo"})
    return _replace_player(state, _add_card(p, top))


def is_duo(a: CardName, b: CardName) -> bool:
    return (a == b and a in ("crab", "boat", "fish")) or {a, b} == {"shark", "swimmer"}


def _play_duo(state: GameState, a: PlayDuo) -> GameState:
    _require(state.phase == "play_duo", "draw a card before playing duos")
    c1, c2 = a.cards
    _require(c1.id != c2.id, "a duo needs two different cards")
    _require(is_duo(c1.name, c2.name), f"{c1.name} + {c2.name} is not a duo")
    hero_id = state.hero_id
    p = state.player(state.active_player_id)
    is_hero = p.player_id == hero_id
    p = _remove_card(_remove_card(p, c1, is_hero), c2, is_hero)
    p = p.model_copy(update={"played_duos": p.played_duos + [c1, c2]})
    state = _replace_player(state, p)
    effect = c1.name

    if effect == "boat":
        return state.model_copy(update={"extra_turn_pending": True})

    if effect == "crab":
        ledger = state.discard_ledger
        if ledger.top("a") is None and ledger.top("b") is None:
            _require(a.crab_card_id is None, "both discard piles are empty: crabs have no effect")
            return state
        _require(a.crab_pile is not None and a.crab_card_id is not None, "choose the card taken from a discard pile")
        assert a.crab_pile is not None and a.crab_card_id is not None
        card = next((c for c in ledger.pile(a.crab_pile) if c.id == a.crab_card_id), None)
        _require(card is not None, f"card {a.crab_card_id} is not in pile {a.crab_pile}")
        state = state.model_copy(update={"discard_ledger": ledger.record_out(a.crab_pile, a.crab_card_id, p.player_id)})
        return _replace_player(state, _add_card(p, card))

    if effect == "fish":
        if state.deck_count == 0:
            _require(a.fish_card is None, "the deck is empty: fish have no effect")
            return state
        _require((a.fish_card is not None) == is_hero, "record the drawn card for yourself only")
        state = state.model_copy(update={"deck_count": state.deck_count - 1})
        return _replace_player(state, _add_card(p, a.fish_card))

    # shark + swimmer: steal a random card from another player's hand
    if a.steal_from is None:
        _require(all(q.hand_size == 0 for q in state.players if q.player_id != p.player_id), "choose who you stole from")
        return state
    _require(a.steal_from != p.player_id, "you can't steal from yourself")
    victim = state.player(a.steal_from)
    _require(victim.hand_size > 0, f"{victim.name} has no cards")
    hero_involved = hero_id in (p.player_id, victim.player_id)
    _require((a.stolen_card is not None) == hero_involved, "record the stolen card only when you are the thief or the victim")
    if hero_involved:
        victim = _remove_card(victim, a.stolen_card, victim.player_id == hero_id)
        thief = _add_card(p, a.stolen_card)
    else:
        # shortcut: we can't tell which card moved, so the victim's seen cards all become unseen (no false certainty).
        victim = victim.model_copy(update={"hand_size": victim.hand_size - 1, "known_hand": []})
        thief = _add_card(p, None)
    return _replace_player(_replace_player(state, victim), thief)


def _end_turn(state: GameState, a: EndTurn) -> GameState:
    _require(state.phase == "play_duo", "draw a card before ending the turn")
    p = state.player(state.active_player_id)
    if a.call:
        _require(state.last_chance_caller is None, "the round is already ending")
        if p.player_id == state.hero_id:
            pts = card_points(all_cards(p))
            _require(pts >= END_ROUND_MIN_POINTS, f"you need {END_ROUND_MIN_POINTS} points to end the round (you have {pts})")
    if a.call == "stop":
        return state.model_copy(update={"phase": "round_end", "round_end_reason": "stop", "extra_turn_pending": False})
    if a.call == "last_chance":
        queue, nxt = [], _next_player(state, p.player_id)
        while nxt != p.player_id:
            queue.append(nxt)
            nxt = _next_player(state, nxt)
        state = state.model_copy(update={"last_chance_caller": p.player_id, "last_chance_queue": queue, "extra_turn_pending": False})
        # the caller's own turn is over; fall through to hand over to the first last-chance player

    if state.deck_count == 0:
        return state.model_copy(update={"phase": "round_end", "round_end_reason": "deck_empty", "extra_turn_pending": False})
    if state.extra_turn_pending:
        return state.model_copy(update={"phase": "draw", "extra_turn_pending": False})
    if state.last_chance_caller is not None:
        if not state.last_chance_queue:
            return state.model_copy(update={"phase": "round_end", "round_end_reason": "last_chance"})
        nxt, rest = state.last_chance_queue[0], state.last_chance_queue[1:]
        return state.model_copy(update={"phase": "draw", "active_player_id": nxt, "last_chance_queue": rest})
    return state.model_copy(update={"phase": "draw", "active_player_id": _next_player(state, p.player_id)})


def _resolve_round(state: GameState, a: ResolveRound) -> GameState:
    _require(state.phase == "round_end", "the round has not ended")
    reason = state.round_end_reason
    assert reason is not None
    if reason == "deck_empty":
        _require(not a.revealed, "the deck ran out: nobody scores, nothing to reveal")
        result = RoundResult(round_number=state.round_number, reason=reason, caller_id=None, caller_won_bet=None,
                             card_points={}, color_bonus={}, awarded={p.player_id: 0 for p in state.players})
        return state.model_copy(update={"phase": "round_start", "history": state.history + [result]})

    players = []
    for p in state.players:
        cards = a.revealed.get(p.player_id, [])
        _require(len(cards) == p.unknown_count, f"reveal exactly {p.unknown_count} unseen cards for {p.name}")
        players.append(p.model_copy(update={"known_hand": p.known_hand + cards}))
    state = state.model_copy(update={"players": players})
    assert_consistent(state)

    pts = {p.player_id: card_points(all_cards(p)) for p in players}
    bonus = {p.player_id: color_bonus(all_cards(p)) for p in players}
    caller = state.active_player_id if reason == "stop" else state.last_chance_caller
    assert caller is not None
    won: bool | None = None
    if reason == "stop":
        awarded = dict(pts)
    else:
        won = all(pts[caller] >= v for k, v in pts.items() if k != caller)
        if won:
            awarded = {k: (pts[k] + bonus[k] if k == caller else bonus[k]) for k in pts}
        else:
            awarded = {k: (bonus[k] if k == caller else pts[k]) for k in pts}

    players = [p.model_copy(update={"current_score": p.current_score + awarded[p.player_id]}) for p in players]
    result = RoundResult(round_number=state.round_number, reason=reason, caller_id=caller, caller_won_bet=won,
                         card_points=pts, color_bonus=bonus, awarded=awarded)
    mermaid_winner = next((p.player_id for p in players if sum(c.name == "mermaid" for c in all_cards(p)) == 4), None)
    leader = max(players, key=lambda p: p.current_score)  # shortcut: ties go to the earlier seat, the rulebook tiebreak is not modelled
    winner = mermaid_winner or (leader.player_id if leader.current_score >= state.target_score else None)
    return state.model_copy(update={
        "players": players, "history": state.history + [result],
        "phase": "game_over" if winner else "round_start", "winner_id": winner,
    })


_HANDLERS = {
    "start_round": _start_round, "draw_deck": _draw_deck, "take_discard": _take_discard,
    "play_duo": _play_duo, "end_turn": _end_turn, "resolve_round": _resolve_round,
}


def apply_action(state: GameState, action: Action) -> GameState:
    """Pure transition: returns a new state, never mutates the input."""
    _require(state.phase != "game_over", "the game is over")
    # the log is append-only, so it is left out of the deep copy (copying it every move is quadratic)
    new = _HANDLERS[action.kind](state.model_copy(update={"log": []}).model_copy(deep=True), action)  # type: ignore[operator]
    assert_consistent(new)
    entry = LogEntry(actor=state.active_player_id if action.kind != "start_round" else "",
                     action=action, top_a=state.discard_ledger.top("a"), top_b=state.discard_ledger.top("b"))
    log = [entry] if action.kind == "start_round" else state.log + [entry]
    return new.model_copy(update={"log": log})
