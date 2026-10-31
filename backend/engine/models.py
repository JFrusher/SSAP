"""Card, player and game state models (base game, 58 cards)."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

CardName = Literal[
    "crab", "boat", "fish", "shark", "swimmer",
    "shell", "octopus", "penguin", "sailor",
    "lighthouse", "shoal", "colony", "captain",
    "mermaid",
]
CardType = Literal["duo", "collector", "multiplier", "mermaid"]
# Mermaids are white; every other card has one of the ten colours below.
Color = Literal[
    "dark_blue", "light_blue", "black", "yellow", "green",
    "purple", "grey", "light_orange", "pink", "orange", "white",
]
NON_WHITE_COLORS: tuple[Color, ...] = (
    "dark_blue", "light_blue", "black", "yellow", "green",
    "purple", "grey", "light_orange", "pink", "orange",
)
Pile = Literal["a", "b"]

DECK_COMPOSITION: dict[CardName, int] = {
    "crab": 9, "boat": 8, "fish": 7, "shark": 5, "swimmer": 5,
    "shell": 6, "octopus": 5, "penguin": 3, "sailor": 2,
    "lighthouse": 1, "shoal": 1, "colony": 1, "captain": 1,
    "mermaid": 4,
}
DECK_SIZE = sum(DECK_COMPOSITION.values())
assert DECK_SIZE == 58

CARD_TYPES: dict[CardName, CardType] = {
    "crab": "duo", "boat": "duo", "fish": "duo", "shark": "duo", "swimmer": "duo",
    "shell": "collector", "octopus": "collector", "penguin": "collector", "sailor": "collector",
    "lighthouse": "multiplier", "shoal": "multiplier", "colony": "multiplier", "captain": "multiplier",
    "mermaid": "mermaid",
}

TARGET_SCORE: dict[int, int] = {2: 40, 3: 35, 4: 30}
END_ROUND_MIN_POINTS = 7


class Card(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: CardName
    color: Color

    @model_validator(mode="after")
    def _mermaids_are_white(self) -> "Card":
        if (self.name == "mermaid") != (self.color == "white"):
            raise ValueError("mermaids are white and only mermaids are white")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def card_type(self) -> CardType:
        return CARD_TYPES[self.name]


class PlayerState(BaseModel):
    player_id: str
    name: str
    is_human: bool
    hand_size: int
    known_hand: list[Card] = []  # complete for the hero; cards seen entering hand for opponents
    played_duos: list[Card] = []
    current_score: int = 0
    # Times this opponent drew blind while a card of that name sat on a discard pile (belief evidence).
    passed_on: dict[CardName, int] = {}

    @property
    def unknown_count(self) -> int:
        return self.hand_size - len(self.known_hand)


class RoundResult(BaseModel):
    round_number: int
    reason: Literal["stop", "last_chance", "deck_empty"]
    caller_id: str | None
    caller_won_bet: bool | None
    card_points: dict[str, int]
    color_bonus: dict[str, int]
    awarded: dict[str, int]


# ---------------------------------------------------------------- actions


class StartRound(BaseModel):
    kind: Literal["start_round"] = "start_round"
    pile_a: Card
    pile_b: Card
    first_player_id: str


class DrawDeck(BaseModel):
    kind: Literal["draw_deck"] = "draw_deck"
    kept: Card | None = None  # hero only: the card kept
    discarded: Card | None = None  # None only when the deck had a single card
    pile: Pile | None = None


class TakeDiscard(BaseModel):
    kind: Literal["take_discard"] = "take_discard"
    pile: Pile


class PlayDuo(BaseModel):
    kind: Literal["play_duo"] = "play_duo"
    cards: tuple[Card, Card]
    crab_pile: Pile | None = None
    crab_card_id: str | None = None
    fish_card: Card | None = None  # hero only: card drawn
    steal_from: str | None = None
    stolen_card: Card | None = None  # required when the hero is thief or victim


class EndTurn(BaseModel):
    kind: Literal["end_turn"] = "end_turn"
    call: Literal["stop", "last_chance"] | None = None


class ResolveRound(BaseModel):
    kind: Literal["resolve_round"] = "resolve_round"
    revealed: dict[str, list[Card]] = {}  # opponent id -> their unknown hand cards


Action = Annotated[
    StartRound | DrawDeck | TakeDiscard | PlayDuo | EndTurn | ResolveRound,
    Field(discriminator="kind"),
]


class LogEntry(BaseModel):
    """One applied action as the hero saw it, with the discard tops just before it (for belief replay)."""

    actor: str
    action: Action
    top_a: Card | None
    top_b: Card | None


Phase = Literal["round_start", "draw", "play_duo", "round_end", "game_over"]


class GameState(BaseModel):
    players: list[PlayerState]
    hero_id: str
    active_player_id: str
    deck_count: int
    discard_ledger: "DiscardLedger"
    phase: Phase
    round_number: int = 0
    target_score: int
    extra_turn_pending: bool = False
    last_chance_caller: str | None = None
    last_chance_queue: list[str] = []
    round_end_reason: Literal["stop", "last_chance", "deck_empty"] | None = None
    history: list[RoundResult] = []
    winner_id: str | None = None
    log: list[LogEntry] = []  # this round's actions, starting with start_round

    def player(self, player_id: str) -> PlayerState:
        for p in self.players:
            if p.player_id == player_id:
                return p
        raise KeyError(player_id)

    @property
    def hero(self) -> PlayerState:
        return self.player(self.hero_id)

    @property
    def opponents(self) -> list[PlayerState]:
        return [p for p in self.players if p.player_id != self.hero_id]


from backend.engine.discard_ledger import DiscardLedger  # noqa: E402  (circular: ledger needs Card)

GameState.model_rebuild()
