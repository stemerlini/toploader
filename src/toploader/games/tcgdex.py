"""International (English) Pokémon cards from the free TCGdex API (https://tcgdex.dev).

TCGdex returns card data, images and daily prices from both Cardmarket (EUR)
and TCGplayer (USD), and needs no API key.
"""

from __future__ import annotations

import asyncio
import re

import httpx

from ..db import Card, now_iso
from ..paths import USER_AGENT
from .base import Catalog, SearchResult

API = "https://api.tcgdex.net/v2/en"

# Finish → TCGplayer price keys, in order of preference.
TCGPLAYER_KEYS = {
    "normal": ["normal", "unlimited", "holofoil"],
    "holo": ["holofoil", "unlimitedHolofoil", "normal"],
    "reverse": ["reverse-holofoil", "reverseHolofoil", "holofoil"],
    "firstEdition": ["1stEditionHolofoil", "1stEditionNormal", "1stEdition"],
}


class TCGdex(Catalog):
    prefix = "en"
    language = "EN"
    sources = ["cardmarket", "tcgplayer"]

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        )
        self._sets: dict[str, str] | None = None

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, **params) -> object:
        response = await self._client.get(f"{API}{path}", params=params or None)
        response.raise_for_status()
        return response.json()

    async def set_names(self) -> dict[str, str]:
        if self._sets is None:
            data = await self._get("/sets")
            self._sets = {s["id"]: s["name"] for s in data}
        return self._sets

    async def search(self, query: str) -> list[SearchResult]:
        """Search by name, or by "<set id> <number>" (e.g. "swsh3 136")."""
        query = query.strip()
        if not query:
            return []
        sets = await self.set_names()
        results: list[SearchResult] = []

        # Exact lookup: "swsh3 136", "swsh3-136" or "sv03.5 199".
        match = re.fullmatch(r"([\w.]+)[\s-]+(\w+)", query)
        if match and match.group(1) in sets:
            card_id = f"{match.group(1)}-{match.group(2)}"
            try:
                card = await self.fetch_card(card_id)
            except httpx.HTTPStatusError:
                pass
            else:
                results.append(
                    SearchResult(card.id, card.name, card.local_id, card.set_id, card.set_name)
                )

        data = await self._get(
            "/cards",
            name=f"like:{query}",
            **{"pagination:itemsPerPage": 100, "sort:field": "name"},
        )
        for item in data:
            set_id = item["id"].rsplit("-", 1)[0]
            results.append(
                SearchResult(
                    id=item["id"],
                    name=item["name"],
                    number=item.get("localId", ""),
                    set_id=set_id,
                    set_name=sets.get(set_id, set_id),
                    has_image=bool(item.get("image")),
                )
            )
        return results

    async def fetch_card(self, card_id: str) -> Card:
        data = await self._get(f"/cards/{card_id}")
        card_set = data.get("set") or {}
        image = data.get("image") or ""
        return Card(
            id=data["id"],
            game="",
            name=data["name"],
            set_id=card_set.get("id", ""),
            set_name=card_set.get("name", ""),
            local_id=str(data.get("localId", "")),
            category=data.get("category", ""),
            rarity=data.get("rarity") or "",
            types=data.get("types") or [],
            image_url=f"{image}/high.png" if image else "",
            variants=data.get("variants") or {},
            pricing=data.get("pricing") or {},
            updated_at=now_iso(),
        )

    async def refresh(self, cards: list[Card], progress=None) -> list[Card]:
        semaphore = asyncio.Semaphore(8)
        done = 0

        async def one(card: Card) -> Card:
            nonlocal done
            async with semaphore:
                try:
                    fresh = await self.fetch_card(card.id)
                except httpx.HTTPError:
                    fresh = card
            done += 1
            if progress:
                progress(done, len(cards))
            return fresh

        return await asyncio.gather(*(one(c) for c in cards))

    def price(self, card: Card, finish: str, source: str) -> float | None:
        if source == "tcgplayer":
            tcg = card.pricing.get("tcgplayer") or {}
            for key in TCGPLAYER_KEYS.get(finish, ["normal"]):
                variant = tcg.get(key)
                if isinstance(variant, dict):
                    value = variant.get("marketPrice") or variant.get("midPrice")
                    if value:
                        return float(value)
            return None

        # Cardmarket lists one product per card; its "-holo" fields are the
        # reverse holo version, the plain fields are the card as printed.
        cm = card.pricing.get("cardmarket") or {}
        keys = ("trend-holo", "avg-holo") if finish == "reverse" else ("trend", "avg")
        for key in keys:
            value = cm.get(key)
            if value:
                return float(value)
        return None

    def price_details(self, card: Card) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        cm = card.pricing.get("cardmarket") or {}
        if cm:
            for label, key in [
                ("Trend", "trend"), ("Avg 7d", "avg7"), ("Avg 30d", "avg30"),
                ("Low", "low"), ("Reverse trend", "trend-holo"), ("Reverse low", "low-holo"),
            ]:
                if cm.get(key):
                    rows.append((f"Cardmarket {label}", f"€{cm[key]:,.2f}"))
        tcg = card.pricing.get("tcgplayer") or {}
        for variant, values in tcg.items():
            if isinstance(values, dict) and values.get("marketPrice"):
                rows.append((f"TCGplayer {variant}", f"${values['marketPrice']:,.2f}"))
        return rows
