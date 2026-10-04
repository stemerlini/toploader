"""Pokémon: one game, searched across the Japanese and international catalogues.

Card ids carry their catalogue as a prefix ("jp:598347", "en:swsh3-136"), so a
Japanese and an English printing of the same card are different cards that
live side by side in one collection.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace

from ..db import Card
from .base import Catalog, Game, SearchResult
from .tcgcsv import TCGCSVJapan, TCGCSVSealed
from .tcgdex import TCGdex


class Pokemon(Game):
    id = "pokemon"
    name = "Pokémon"
    icon = "◓"
    search_hint = "Name, number or set: Pikachu, 270/SM-P, s4a, sm10 sealed, 151 booster box…"
    MAX_PER_CATALOG = 150  # so a long Japanese list doesn't bury the English results

    def __init__(self) -> None:
        # Listed in this order in search results: Japanese, international, sealed.
        self.catalogs: dict[str, Catalog] = {
            c.prefix: c for c in (TCGCSVJapan(), TCGdex(), TCGCSVSealed())
        }

    async def close(self) -> None:
        for catalog in self.catalogs.values():
            await catalog.close()

    def _split(self, card_id: str) -> tuple[Catalog, str]:
        prefix, _, raw = card_id.partition(":")
        return self.catalogs[prefix], raw

    def _own(self, card: Card, catalog: Catalog) -> Card:
        return replace(card, id=f"{catalog.prefix}:{card.id}", game=self.id)

    def _raw(self, card: Card) -> Card:
        return replace(card, id=card.id.partition(":")[2])

    async def prepare(self, progress=None) -> None:
        for catalog in self.catalogs.values():
            await catalog.prepare(progress)

    async def search(self, query: str) -> list[SearchResult]:
        catalogs = list(self.catalogs.values())
        found = await asyncio.gather(*(c.search(query) for c in catalogs),
                                     return_exceptions=True)
        results: list[SearchResult] = []
        errors = [items for items in found if isinstance(items, BaseException)]
        # Only cap when several catalogues answered, so browsing one set ("s4a")
        # shows all of it.
        answered = sum(1 for items in found if not isinstance(items, BaseException) and items)
        limit = self.MAX_PER_CATALOG if answered > 1 else None
        for catalog, items in zip(catalogs, found, strict=True):
            if isinstance(items, BaseException):
                continue
            results += [
                replace(r, id=f"{catalog.prefix}:{r.id}", language=catalog.language)
                for r in items[:limit]
            ]
        if errors and not results:
            raise errors[0]
        return results

    async def fetch_card(self, card_id: str) -> Card:
        catalog, raw = self._split(card_id)
        return self._own(await catalog.fetch_card(raw), catalog)

    async def refresh(self, cards: list[Card], progress=None) -> list[Card]:
        fresh: list[Card] = []
        for prefix, catalog in self.catalogs.items():
            mine = [self._raw(c) for c in cards if c.id.startswith(f"{prefix}:")]
            if mine:
                fresh += [self._own(c, catalog) for c in await catalog.refresh(mine)]
        return fresh

    def price(self, card: Card, finish: str, preferred: str) -> tuple[float, str] | None:
        catalog, _ = self._split(card.id)
        order = sorted(catalog.sources, key=lambda s: s != preferred)
        for source in order:
            value = catalog.price(card, finish, source)
            if value is not None:
                return value, source
        return None

    def price_details(self, card: Card) -> list[tuple[str, str]]:
        return self._split(card.id)[0].price_details(card)

    def card_language(self, card: Card) -> str:
        return self._split(card.id)[0].language
