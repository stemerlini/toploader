"""What a collection line is worth, shared by the app and `toploader summary`."""

from __future__ import annotations

from dataclasses import dataclass

from .currency import SOURCE_CURRENCY, Rates
from .db import Entry
from .games.base import Game


def unit_value(entry: Entry, game: Game, source: str, currency: str,
               rates: Rates) -> float | None:
    """One copy's value in `currency`: the user's own valuation if set,
    otherwise the market price (preferring `source`)."""
    if entry.my_value is not None:
        return rates.convert(entry.my_value, entry.my_value_currency, currency)
    found = game.price(entry.card, entry.finish, source)
    if found is None:
        return None
    native, used = found
    return rates.convert(native, SOURCE_CURRENCY[used], currency)


@dataclass
class Summary:
    copies: int
    unique: int
    value: float
    currency: str


def summarize(entries: list[Entry], game: Game, source: str, currency: str,
              rates: Rates) -> Summary:
    return Summary(
        copies=sum(e.quantity for e in entries),
        unique=len({e.card.id for e in entries}),
        value=sum((unit_value(e, game, source, currency, rates) or 0) * e.quantity
                  for e in entries),
        currency=currency,
    )
