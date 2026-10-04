"""SQLite storage for the card catalogue cache and the user's inventory."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .paths import DATA_DIR

SEALED = "Sealed"  # Card.category of sealed products (boxes, packs, ETBs…)

CONDITIONS = ["M", "NM", "EX", "GD", "LP", "PL", "PO"]
SEALED_CONDITIONS = ["S", "SD", "O"]
CONDITION_NAMES = {
    "S": "Sealed",
    "SD": "Sealed, damaged packaging",
    "O": "Opened",
    "M": "Mint",
    "NM": "Near Mint",
    "EX": "Excellent",
    "GD": "Good",
    "LP": "Light Played",
    "PL": "Played",
    "PO": "Poor",
}

# Print run of sealed products: TCGplayer usually lists one product for all
# print runs, so a first-print box needs its own line and often a manual value.
PRINT_RUNS = {"": "Unknown", "first": "First print", "reprint": "Reprint"}

FINISHES = ["normal", "holo", "reverse", "firstEdition"]
FINISH_NAMES = {
    "normal": "Normal",
    "holo": "Holo",
    "reverse": "Reverse Holo",
    "firstEdition": "1st Edition",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    id          TEXT NOT NULL,
    game        TEXT NOT NULL,
    name        TEXT NOT NULL,
    set_id      TEXT,
    set_name    TEXT,
    local_id    TEXT,
    category    TEXT,
    rarity      TEXT,
    types       TEXT,          -- JSON list
    image_url   TEXT,
    variants    TEXT,          -- JSON object
    pricing     TEXT,          -- JSON object as returned by the API
    updated_at  TEXT,
    PRIMARY KEY (game, id)
);

CREATE TABLE IF NOT EXISTS inventory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game            TEXT NOT NULL,
    card_id         TEXT NOT NULL,
    finish          TEXT NOT NULL DEFAULT 'normal',
    condition       TEXT NOT NULL DEFAULT 'NM',
    language        TEXT NOT NULL DEFAULT 'EN',
    quantity        INTEGER NOT NULL DEFAULT 1,
    purchase_price  REAL,
    purchase_currency TEXT NOT NULL DEFAULT 'EUR',
    print_run       TEXT NOT NULL DEFAULT '',
    my_value        REAL,              -- the user's own valuation, overrides the market price
    my_value_currency TEXT NOT NULL DEFAULT 'EUR',
    notes           TEXT NOT NULL DEFAULT '',
    added_at        TEXT NOT NULL,
    FOREIGN KEY (game, card_id) REFERENCES cards (game, id)
);
"""


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class Card:
    id: str
    game: str
    name: str
    set_id: str = ""
    set_name: str = ""
    local_id: str = ""
    category: str = ""
    rarity: str = ""
    types: list[str] = field(default_factory=list)
    image_url: str = ""
    variants: dict = field(default_factory=dict)
    pricing: dict = field(default_factory=dict)
    updated_at: str = ""

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Card:
        return cls(
            id=row["id"],
            game=row["game"],
            name=row["name"],
            set_id=row["set_id"] or "",
            set_name=row["set_name"] or "",
            local_id=row["local_id"] or "",
            category=row["category"] or "",
            rarity=row["rarity"] or "",
            types=json.loads(row["types"] or "[]"),
            image_url=row["image_url"] or "",
            variants=json.loads(row["variants"] or "{}"),
            pricing=json.loads(row["pricing"] or "{}"),
            updated_at=row["updated_at"] or "",
        )

    @property
    def is_sealed(self) -> bool:
        return self.category == SEALED

    @property
    def conditions(self) -> list[str]:
        return SEALED_CONDITIONS if self.is_sealed else CONDITIONS

    @property
    def available_finishes(self) -> list[str]:
        finishes = [f for f in FINISHES if self.variants.get(f)]
        return finishes or ["normal"]


@dataclass
class Entry:
    """One inventory line: a card in a given finish/condition/language."""

    id: int
    card: Card
    finish: str
    condition: str
    language: str
    quantity: int
    purchase_price: float | None
    purchase_currency: str
    notes: str
    added_at: str
    print_run: str = ""
    my_value: float | None = None
    my_value_currency: str = "EUR"


class Database:
    def __init__(self, path: Path | None = None) -> None:
        path = path or DATA_DIR / "collection.db"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()
        self.conn.execute("PRAGMA foreign_keys = ON")

    def _migrate(self) -> None:
        columns = {r["name"] for r in self.conn.execute("PRAGMA table_info(inventory)")}
        for column, definition in [
            ("purchase_currency", "TEXT NOT NULL DEFAULT 'EUR'"),
            ("print_run", "TEXT NOT NULL DEFAULT ''"),
            ("my_value", "REAL"),
            ("my_value_currency", "TEXT NOT NULL DEFAULT 'EUR'"),
        ]:
            if column not in columns:
                self.conn.execute(f"ALTER TABLE inventory ADD COLUMN {column} {definition}")
        # Japanese and English Pokémon used to be separate games; they are now one
        # game whose card ids carry the catalogue ("jp:…", "en:…").
        for table, column in (("cards", "id"), ("inventory", "card_id")):
            self.conn.execute(
                f"UPDATE {table} SET {column} = 'jp:' || {column}, game = 'pokemon' "
                "WHERE game = 'pokemon-jp'"
            )
            self.conn.execute(
                f"UPDATE {table} SET {column} = 'en:' || {column} "
                f"WHERE game = 'pokemon' AND INSTR({column}, ':') = 0"
            )

    # -- cards -------------------------------------------------------------

    def upsert_card(self, card: Card) -> None:
        self.conn.execute(
            """
            INSERT INTO cards (id, game, name, set_id, set_name, local_id, category,
                               rarity, types, image_url, variants, pricing, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (game, id) DO UPDATE SET
                name = excluded.name, set_id = excluded.set_id,
                set_name = excluded.set_name, local_id = excluded.local_id,
                category = excluded.category, rarity = excluded.rarity,
                types = excluded.types, image_url = excluded.image_url,
                variants = excluded.variants, pricing = excluded.pricing,
                updated_at = excluded.updated_at
            """,
            (
                card.id, card.game, card.name, card.set_id, card.set_name,
                card.local_id, card.category, card.rarity, json.dumps(card.types),
                card.image_url, json.dumps(card.variants), json.dumps(card.pricing),
                card.updated_at or now_iso(),
            ),
        )
        self.conn.commit()

    def owned_card_ids(self, game: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT card_id FROM inventory WHERE game = ?", (game,)
        )
        return [r["card_id"] for r in rows]

    # -- inventory -----------------------------------------------------------

    def add_entry(
        self,
        card: Card,
        finish: str,
        condition: str,
        language: str,
        quantity: int,
        purchase_price: float | None = None,
        purchase_currency: str = "EUR",
        notes: str = "",
        print_run: str = "",
        my_value: float | None = None,
        my_value_currency: str = "EUR",
    ) -> int:
        """Add cards; merges into an existing identical line if there is one."""
        self.upsert_card(card)
        existing = self.conn.execute(
            """SELECT id FROM inventory WHERE game = ? AND card_id = ? AND finish = ?
               AND condition = ? AND language = ? AND print_run = ?""",
            (card.game, card.id, finish, condition, language, print_run),
        ).fetchone()
        if existing:
            self.conn.execute(
                "UPDATE inventory SET quantity = quantity + ? WHERE id = ?",
                (quantity, existing["id"]),
            )
            self.conn.commit()
            return existing["id"]
        cur = self.conn.execute(
            """INSERT INTO inventory (game, card_id, finish, condition, language,
                                      quantity, purchase_price, purchase_currency,
                                      notes, added_at, print_run, my_value,
                                      my_value_currency)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (card.game, card.id, finish, condition, language, quantity,
             purchase_price, purchase_currency, notes, now_iso(), print_run, my_value,
             my_value_currency),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_entry(self, entry_id: int, **fields) -> None:
        allowed = {"finish", "condition", "language", "quantity", "purchase_price",
                   "purchase_currency", "notes", "print_run", "my_value", "my_value_currency"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return
        assignments = ", ".join(f"{k} = ?" for k in sets)
        self.conn.execute(
            f"UPDATE inventory SET {assignments} WHERE id = ?", (*sets.values(), entry_id)
        )
        self.conn.commit()

    def delete_entry(self, entry_id: int) -> None:
        self.conn.execute("DELETE FROM inventory WHERE id = ?", (entry_id,))
        self.conn.commit()

    def entries(self, game: str) -> list[Entry]:
        rows = self.conn.execute(
            """
            SELECT i.id AS entry_id, i.finish, i.condition, i.language, i.quantity,
                   i.purchase_price, i.purchase_currency, i.notes, i.added_at,
                   i.print_run, i.my_value, i.my_value_currency, c.*
            FROM inventory i JOIN cards c ON c.game = i.game AND c.id = i.card_id
            WHERE i.game = ?
            ORDER BY c.set_name, CAST(c.local_id AS INTEGER), c.local_id, c.name
            """,
            (game,),
        )
        return [
            Entry(
                id=r["entry_id"],
                card=Card.from_row(r),
                finish=r["finish"],
                condition=r["condition"],
                language=r["language"],
                quantity=r["quantity"],
                purchase_price=r["purchase_price"],
                purchase_currency=r["purchase_currency"],
                notes=r["notes"],
                added_at=r["added_at"],
                print_run=r["print_run"],
                my_value=r["my_value"],
                my_value_currency=r["my_value_currency"],
            )
            for r in rows
        ]
