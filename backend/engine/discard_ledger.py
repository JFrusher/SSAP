"""Immutable log of every card entering or leaving the two discard piles.

The piles themselves are derived from the log, so there is exactly one source of truth.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict

from backend.engine.models import Card, Pile


class IllegalAction(ValueError):
    """Raised when an action breaks the rules or contradicts the tracked state."""


class LedgerEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    direction: Literal["in", "out"]
    pile: Pile
    card: Card
    player_id: str | None  # None for the two cards flipped at round setup


class DiscardLedger(BaseModel):
    model_config = ConfigDict(frozen=True)

    entries: tuple[LedgerEntry, ...] = ()

    def pile(self, pile: Pile) -> list[Card]:
        """Pile contents, bottom first (last element is the visible top card)."""
        stack: list[Card] = []
        for e in self.entries:
            if e.pile != pile:
                continue
            if e.direction == "in":
                stack.append(e.card)
            else:
                stack = [c for c in stack if c.id != e.card.id]
        return stack

    def top(self, pile: Pile) -> Card | None:
        stack = self.pile(pile)
        return stack[-1] if stack else None

    def record_in(self, pile: Pile, card: Card, player_id: str | None) -> "DiscardLedger":
        return DiscardLedger(entries=self.entries + (LedgerEntry(direction="in", pile=pile, card=card, player_id=player_id),))

    def record_out(self, pile: Pile, card_id: str, player_id: str) -> "DiscardLedger":
        match = [c for c in self.pile(pile) if c.id == card_id]
        if not match:
            raise IllegalAction(f"card {card_id} is not in discard pile {pile}")
        return DiscardLedger(entries=self.entries + (LedgerEntry(direction="out", pile=pile, card=match[0], player_id=player_id),))
