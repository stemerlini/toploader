"""The collection database: migrations from older formats, merging lines."""

import sqlite3

import pytest

from toploader.db import Card, Database

# The inventory table as it was before purchase currency, print runs and
# personal valuations existed, when JP and EN were separate games.
OLD_SCHEMA = """
CREATE TABLE cards (
    id TEXT NOT NULL, game TEXT NOT NULL, name TEXT NOT NULL, set_id TEXT, set_name TEXT,
    local_id TEXT, category TEXT, rarity TEXT, types TEXT, image_url TEXT, variants TEXT,
    pricing TEXT, updated_at TEXT, PRIMARY KEY (game, id)
);
CREATE TABLE inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT, game TEXT NOT NULL, card_id TEXT NOT NULL,
    finish TEXT NOT NULL DEFAULT 'normal', condition TEXT NOT NULL DEFAULT 'NM',
    language TEXT NOT NULL DEFAULT 'EN', quantity INTEGER NOT NULL DEFAULT 1,
    purchase_price REAL, notes TEXT NOT NULL DEFAULT '', added_at TEXT NOT NULL,
    FOREIGN KEY (game, card_id) REFERENCES cards (game, id)
);
INSERT INTO cards (id, game, name) VALUES ('598347', 'pokemon-jp', 'Red''s Pikachu');
INSERT INTO cards (id, game, name) VALUES ('base1-4', 'pokemon', 'Charizard');
INSERT INTO inventory (game, card_id, finish, language, quantity, added_at)
    VALUES ('pokemon-jp', '598347', 'holo', 'JP', 1, '2026-10-04');
INSERT INTO inventory (game, card_id, finish, language, quantity, added_at)
    VALUES ('pokemon', 'base1-4', 'holo', 'EN', 2, '2026-10-04');
"""


def test_old_collection_is_migrated(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(OLD_SCHEMA)
    conn.close()

    db = Database(path)
    entries = {e.card.id: e for e in db.entries("pokemon")}
    assert set(entries) == {"jp:598347", "en:base1-4"}
    assert entries["jp:598347"].card.name == "Red's Pikachu"
    assert entries["en:base1-4"].quantity == 2
    pikachu = entries["jp:598347"]
    assert (pikachu.purchase_currency, pikachu.print_run, pikachu.my_value) == ("EUR", "", None)

    # Opening it again changes nothing.
    db.conn.close()
    assert {e.card.id for e in Database(path).entries("pokemon")} == {"jp:598347", "en:base1-4"}


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "collection.db")


BOX = Card(id="jp:201", game="pokemon", name="Shiny Star V Booster Box", category="Sealed")


def test_identical_lines_are_merged(db):
    first = db.add_entry(BOX, "normal", "S", "JP", 1, print_run="reprint")
    again = db.add_entry(BOX, "normal", "S", "JP", 2, print_run="reprint")
    assert first == again
    [entry] = db.entries("pokemon")
    assert entry.quantity == 3


def test_print_runs_are_separate_lines(db):
    db.add_entry(BOX, "normal", "S", "JP", 1, print_run="first", my_value=420.0)
    db.add_entry(BOX, "normal", "S", "JP", 1, print_run="reprint")
    runs = {e.print_run: e for e in db.entries("pokemon")}
    assert set(runs) == {"first", "reprint"}
    assert runs["first"].my_value == 420.0 and runs["reprint"].my_value is None


def test_update_only_touches_known_fields(db):
    entry_id = db.add_entry(BOX, "normal", "S", "JP", 1)
    db.update_entry(entry_id, quantity=5, my_value=99.0, my_value_currency="GBP", game="evil")
    [entry] = db.entries("pokemon")
    assert (entry.quantity, entry.my_value, entry.my_value_currency) == (5, 99.0, "GBP")


def test_delete(db):
    entry_id = db.add_entry(BOX, "normal", "S", "JP", 1)
    db.delete_entry(entry_id)
    assert db.entries("pokemon") == []
