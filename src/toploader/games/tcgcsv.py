"""Pokémon cards and sealed products from TCGCSV (https://tcgcsv.com).

TCGCSV mirrors TCGplayer once a day: every set, promo set, card and sealed
product (booster boxes, packs, ETBs…) with English names, images and USD market
prices. There is no search endpoint, so the product list is downloaded once into
a local SQLite catalogue (in the cache folder) and refreshed weekly.

Two catalogues use it:
- Japanese cards: TCGplayer's "Pokemon Japan" category, singles and sealed.
- International sealed products: the "Pokemon" category, sealed only, since
  international singles come from TCGdex (which also has Cardmarket prices).
"""

from __future__ import annotations

import asyncio
import re
import sqlite3
from datetime import UTC, datetime, timedelta

import httpx

from ..db import SEALED, Card, now_iso
from ..paths import CACHE_DIR, USER_AGENT
from .base import Catalog, SearchResult

API = "https://tcgcsv.com/tcgplayer"
MAX_AGE = timedelta(days=7)

# Finish → TCGplayer sub-type names, in order of preference.
SUBTYPES = {
    "normal": ["Normal", "Holofoil"],
    "holo": ["Holofoil", "Normal"],
    "reverse": ["Reverse Holofoil", "Holofoil"],
    "firstEdition": ["1st Edition Holofoil", "1st Edition", "1st Edition Normal"],
}

# Sealed product type from its name; first match wins, so "Booster Box Case"
# is checked before "Booster Box" and "Booster Box" before "Booster".
SEALED_KINDS = [
    (r"\bcase\b", "Case"),
    (r"booster box|booster display|\bdisplay\b", "Booster Box"),
    (r"elite trainer box|\betb\b", "Elite Trainer Box"),
    (r"booster bundle", "Booster Bundle"),
    (r"promo (card )?pack|promo pack", "Promo Pack"),
    (r"booster pack|\bpack\b|\bbooster\b", "Booster Pack"),
    (r"\btins?\b", "Tin"),
    (r"blister", "Blister"),
    (r"\bdecks?\b|starter set|trainer kit|battle academy", "Deck"),
    (r"collection|premium|\bbox\b|special set|chest|showcase|calendar", "Collection Box"),
    (r"binder|card file|sleeve|playmat|portfolio", "Accessory"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY, name TEXT, abbreviation TEXT, published TEXT
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY, group_id INTEGER, name TEXT, number TEXT,
    rarity TEXT, card_type TEXT, image TEXT,
    sealed INTEGER NOT NULL DEFAULT 0   -- 1 for boxes, packs, ETBs…
);
CREATE INDEX IF NOT EXISTS products_number ON products (number);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


def _category(card_type: str) -> str:
    if card_type.startswith("Trainer"):
        return "Trainer"
    if card_type.endswith("Energy"):
        return "Energy"
    return "Pokemon"


def sealed_kind(name: str) -> str:
    lowered = name.lower()
    for pattern, kind in SEALED_KINDS:
        if re.search(pattern, lowered):
            return kind
    return "Sealed Product"


def _clean_name(name: str) -> str:
    """Drop the number TCGplayer appends to card names ("Pikachu - 270/SM-P")."""
    return re.sub(r"\s+-\s+[\w/+-]*\d[\w/+-]*(?=\s*\(|$)", "", name)


class TCGCSV(Catalog):
    sources = ["tcgplayer"]
    category: int = 0  # TCGplayer category id
    singles = True  # include single cards
    filename = ""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        )
        path = CACHE_DIR / self.filename
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self._lock = asyncio.Lock()

    async def close(self) -> None:
        await self._client.aclose()
        self.db.close()

    async def _get(self, path: str) -> list[dict]:
        response = await self._client.get(f"{API}/{self.category}{path}")
        response.raise_for_status()
        return response.json().get("results") or []

    # -- catalogue -----------------------------------------------------------

    def _synced_at(self) -> datetime | None:
        row = self.db.execute("SELECT value FROM meta WHERE key = 'synced_at'").fetchone()
        return datetime.fromisoformat(row["value"]) if row else None

    async def prepare(self, progress=None) -> None:
        async with self._lock:
            synced = self._synced_at()
            if synced and datetime.now(UTC) - synced < MAX_AGE:
                return
            try:
                await self._sync(progress)
            except httpx.HTTPError:
                if synced is None:
                    raise  # no catalogue at all: surface the error
                # Otherwise keep using the old catalogue.

    async def _sync(self, progress=None) -> None:
        groups = await self._get("/groups")
        semaphore = asyncio.Semaphore(8)
        done = 0
        rows: list[tuple] = []

        async def one(group: dict) -> None:
            nonlocal done
            async with semaphore:
                products = await self._get(f"/{group['groupId']}/products")
            for p in products:
                ext = {e["name"]: e["value"] for e in p.get("extendedData") or []}
                image = p.get("imageUrl", "")
                # Every card has a type or rarity; old Japanese cards often have
                # no number. Sealed products only carry a description.
                if {"Number", "CardType", "Rarity"} & ext.keys():
                    if self.singles:
                        rows.append((
                            p["productId"], group["groupId"], p["name"],
                            ext.get("Number", "").upper(),
                            ext.get("Rarity", ""), ext.get("CardType", ""), image, 0,
                        ))
                else:
                    rows.append((
                        p["productId"], group["groupId"], p["name"], "",
                        "", sealed_kind(p["name"]), image, 1,
                    ))
            done += 1
            if progress:
                progress(done, len(groups))

        await asyncio.gather(*(one(g) for g in groups))
        with self.db:
            self.db.execute("DELETE FROM groups")
            self.db.execute("DELETE FROM products")
            self.db.executemany(
                "INSERT INTO groups VALUES (?, ?, ?, ?)",
                [(g["groupId"], g["name"], g.get("abbreviation") or "",
                  g.get("publishedOn") or "") for g in groups],
            )
            self.db.executemany(
                "INSERT OR REPLACE INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows
            )
            self.db.execute("INSERT OR REPLACE INTO meta VALUES ('synced_at', ?)", (now_iso(),))

    # -- search --------------------------------------------------------------

    _SELECT = """
        SELECT p.*, g.name AS group_name, g.abbreviation FROM products p
        JOIN groups g ON g.id = p.group_id
    """

    async def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        rows: list[sqlite3.Row] = []

        # "270/SM-P", "270/sm-p", "sm-p 270", "SM-P-270"
        number = re.fullmatch(r"(\d+)\s*/\s*([\w+-]+)", query)
        set_first = re.fullmatch(r"([\w+-]+?)[\s-]+(\d+)", query)
        if number or set_first:
            num, code = number.groups() if number else set_first.groups()[::-1]
            # CAST reads the leading digits, so "71" matches "071/SM-P".
            # The code after "/" is either the promo set (SM-P) or the set size (103).
            rows = self.db.execute(
                self._SELECT + "WHERE p.sealed = 0 AND CAST(p.number AS INTEGER) = ? AND ("
                "UPPER(SUBSTR(p.number, INSTR(p.number, '/') + 1)) = ? "
                "OR UPPER(g.abbreviation) = ?) ORDER BY g.published DESC",
                (int(num), code.upper(), code.upper()),
            ).fetchall()

        if not rows:
            rows = self._search_words(query.split())

        return [
            SearchResult(
                id=str(r["id"]),
                name=r["name"] if r["sealed"] else _clean_name(r["name"]),
                number=r["number"],
                set_id=str(r["group_id"]),
                set_name=r["group_name"],
                has_image=bool(r["image"]),
                sealed=bool(r["sealed"]),
            )
            for r in rows
        ]

    def _search_words(self, words: list[str]) -> list[sqlite3.Row]:
        """Free-text search.

        - A word that is a set code ("s4a", "SM10", "sv2a") limits the results
          to that expansion; with no other words it lists the whole set.
        - The word "sealed" keeps only sealed products.
        - Other words must all appear in the product or set name, and at least
          one in the product name itself, so a set called "Charizard VSTAR Deck"
          doesn't return every card in it.
        """
        sealed_only = any(w.lower() == "sealed" for w in words)
        words = [w for w in words if w.lower() != "sealed"]
        codes = {r[0] for r in self.db.execute(
            "SELECT DISTINCT UPPER(abbreviation) FROM groups WHERE abbreviation != ''")}
        set_codes = [w.upper() for w in words if w.upper() in codes]
        words = [w for w in words if w.upper() not in codes]

        conditions: list[str] = []
        params: list[str] = []
        if set_codes:
            conditions.append(
                f"UPPER(g.abbreviation) IN ({', '.join('?' * len(set_codes))})")
            params += set_codes
            for w in words:
                conditions.append("p.name LIKE ?")
                params.append(f"%{w}%")
        elif words:
            for w in words:
                conditions.append("(p.name LIKE ? OR g.name LIKE ?)")
                params += [f"%{w}%", f"%{w}%"]
            conditions.append("(" + " OR ".join("p.name LIKE ?" for _ in words) + ")")
            params += [f"%{w}%" for w in words]
        elif not sealed_only:
            return []
        if sealed_only:
            conditions.append("p.sealed = 1")

        # Browsing a set: its sealed products first, then the cards in number
        # order. Otherwise newest sets first.
        order = "p.sealed DESC, " if set_codes else ""
        return self.db.execute(
            self._SELECT + f"WHERE {' AND '.join(conditions) or '1'} "
            f"ORDER BY {order}g.published DESC, CAST(p.number AS INTEGER), p.number "
            "LIMIT 600",
            params,
        ).fetchall()

    # -- cards & prices --------------------------------------------------------

    async def _prices(self, group_id: str) -> dict[str, dict[str, dict]]:
        """productId → {subTypeName: price row} for one set."""
        result: dict[str, dict[str, dict]] = {}
        for row in await self._get(f"/{group_id}/prices"):
            result.setdefault(str(row["productId"]), {})[row["subTypeName"]] = {
                k: row.get(k) for k in ("lowPrice", "midPrice", "highPrice", "marketPrice")
            }
        return result

    def _card(self, card_id: str, prices: dict[str, dict]) -> Card:
        row = self.db.execute(self._SELECT + "WHERE p.id = ?", (int(card_id),)).fetchone()
        if row is None:
            raise KeyError(card_id)
        image = row["image"] or ""
        common = dict(
            id=card_id,
            game="",
            set_id=str(row["group_id"]),
            set_name=row["group_name"],
            image_url=image.replace("_200w.", "_in_1000x1000.") if image else "",
            pricing={"tcgplayer": prices, "url": f"https://www.tcgplayer.com/product/{card_id}"},
            updated_at=now_iso(),
        )
        if row["sealed"]:
            # Sealed products: the product type (Booster Box, ETB…) goes in rarity.
            return Card(name=row["name"], category=SEALED, rarity=row["card_type"],
                        variants={"normal": True}, **common)

        subtypes = set(prices)
        variants = {
            "normal": "Normal" in subtypes,
            "holo": "Holofoil" in subtypes,
            "reverse": "Reverse Holofoil" in subtypes,
            "firstEdition": any(s.startswith("1st Edition") for s in subtypes),
        }
        card_type = row["card_type"] or ""
        return Card(
            name=_clean_name(row["name"]),
            local_id=row["number"],
            category=_category(card_type),
            rarity=row["rarity"] or "",
            types=[card_type] if _category(card_type) == "Pokemon" and card_type else [],
            variants=variants,
            **common,
        )

    async def fetch_card(self, card_id: str) -> Card:
        await self.prepare()
        row = self.db.execute("SELECT group_id FROM products WHERE id = ?",
                              (int(card_id),)).fetchone()
        if row is None:
            raise KeyError(card_id)
        prices = await self._prices(str(row["group_id"]))
        return self._card(card_id, prices.get(card_id, {}))

    async def refresh(self, cards: list[Card], progress=None) -> list[Card]:
        await self.prepare()
        group_ids = sorted({c.set_id for c in cards})
        semaphore = asyncio.Semaphore(8)

        async def one(group_id: str) -> tuple[str, dict]:
            async with semaphore:
                try:
                    return group_id, await self._prices(group_id)
                except httpx.HTTPError:
                    return group_id, {}

        prices = dict(await asyncio.gather(*(one(g) for g in group_ids)))
        fresh: list[Card] = []
        for card in cards:
            group_prices = prices.get(card.set_id)
            if not group_prices:
                fresh.append(card)  # keep the old prices when the download failed
                continue
            try:
                fresh.append(self._card(card.id, group_prices.get(card.id, {})))
            except KeyError:
                fresh.append(card)
        return fresh

    def price(self, card: Card, finish: str, source: str) -> float | None:
        prices = card.pricing.get("tcgplayer") or {}
        for subtype in SUBTYPES.get(finish, ["Normal"]) + list(prices):
            row = prices.get(subtype)
            if row and (row.get("marketPrice") or row.get("midPrice")):
                return float(row.get("marketPrice") or row["midPrice"])
        return None

    def price_details(self, card: Card) -> list[tuple[str, str]]:
        rows = []
        for subtype, values in (card.pricing.get("tcgplayer") or {}).items():
            label = "TCGplayer" if card.category == SEALED else f"TCGplayer {subtype}"
            for name, key in [("market", "marketPrice"), ("low", "lowPrice"),
                              ("mid", "midPrice")]:
                if values.get(key):
                    rows.append((f"{label} {name}", f"${values[key]:,.2f}"))
        return rows


class TCGCSVJapan(TCGCSV):
    """Japanese singles and sealed products."""

    prefix = "jp"
    language = "JP"
    category = 85
    filename = "tcgcsv-pokemon-japan.db"


class TCGCSVSealed(TCGCSV):
    """International sealed products (singles come from TCGdex)."""

    prefix = "ens"
    language = "EN"
    category = 3
    singles = False
    filename = "tcgcsv-pokemon-sealed.db"
