"""Interfaces for games (what the app shows) and catalogues (where card data comes from)."""

from __future__ import annotations

from dataclasses import dataclass

from ..db import Card

SOURCE_NAMES = {"cardmarket": "Cardmarket", "tcgplayer": "TCGplayer"}


@dataclass
class SearchResult:
    id: str
    name: str
    number: str
    set_id: str
    set_name: str
    has_image: bool = True
    language: str = ""
    sealed: bool = False


class Catalog:
    """One card database, e.g. the Japanese or the international printings.

    Catalogues work with their own raw card ids; the game prefixes them.
    """

    prefix: str = ""  # added to card ids, e.g. "jp" → "jp:598347"
    language: str = "EN"  # language its cards are printed in
    sources: list[str] = []  # price sources it has, in order of preference

    async def prepare(self, progress=None) -> None:
        """Download whatever is needed before searching (e.g. a card list)."""

    async def close(self) -> None: ...

    async def search(self, query: str) -> list[SearchResult]:
        raise NotImplementedError

    async def fetch_card(self, card_id: str) -> Card:
        raise NotImplementedError

    async def refresh(self, cards: list[Card], progress=None) -> list[Card]:
        """Re-download card data (prices included) for the given cards."""
        raise NotImplementedError

    def price(self, card: Card, finish: str, source: str) -> float | None:
        """Market price of one copy from `source`, in that source's currency."""
        raise NotImplementedError

    def price_details(self, card: Card) -> list[tuple[str, str]]:
        """(label, formatted value) pairs shown in the preview."""
        return []


class Game:
    id: str = ""
    name: str = ""
    icon: str = ""
    search_hint: str = "Card name"

    async def prepare(self, progress=None) -> None: ...

    async def close(self) -> None: ...

    async def search(self, query: str) -> list[SearchResult]:
        raise NotImplementedError

    async def fetch_card(self, card_id: str) -> Card:
        raise NotImplementedError

    async def refresh(self, cards: list[Card], progress=None) -> list[Card]:
        raise NotImplementedError

    def price(self, card: Card, finish: str, preferred: str) -> tuple[float, str] | None:
        """(unit price, source it came from), trying `preferred` first."""
        raise NotImplementedError

    def price_details(self, card: Card) -> list[tuple[str, str]]:
        return []

    def card_language(self, card: Card) -> str:
        """Language the card was printed in, used as the default for new copies."""
        return "EN"
