"""Shared test setup.

Everything runs offline: the app's data folder points at a temporary
directory, and the price sources are replaced with small in-memory fixtures.
"""

import os
import tempfile

# Must be set before toploader is imported: paths.py reads it at import time.
os.environ["TOPLOADER_HOME"] = tempfile.mkdtemp(prefix="toploader-tests-")
# textual-image can't probe a terminal under pytest; give it foot's cell size.
os.environ["TEXTUAL_CELL_WIDTH"] = "7"
os.environ["TEXTUAL_CELL_HEIGHT"] = "17"

import pytest  # noqa: E402

from toploader.games.tcgcsv import TCGCSV  # noqa: E402

# -- A miniature TCGCSV "Pokemon Japan" category -------------------------------

GROUPS = [
    {"groupId": 1, "name": "SM-P: Sun & Moon Promos", "abbreviation": "SM-P",
     "publishedOn": "2016-11-01T00:00:00"},
    {"groupId": 2, "name": "S4a: Shiny Star V", "abbreviation": "S4a",
     "publishedOn": "2020-11-20T00:00:00"},
    {"groupId": 3, "name": "Expansion Pack", "abbreviation": "",
     "publishedOn": "1996-10-20T00:00:00"},
    {"groupId": 4, "name": "sC: Charizard VSTAR vs Rayquaza VMAX Special Deck Set",
     "abbreviation": "sC", "publishedOn": "2022-12-02T00:00:00"},
]


def card(pid, name, number=None, rarity="Common", card_type="Lightning"):
    ext = [{"name": "Rarity", "value": rarity}, {"name": "CardType", "value": card_type}]
    if number:
        ext.append({"name": "Number", "value": number})
    return {"productId": pid, "name": name, "extendedData": ext,
            "imageUrl": f"https://img.example/{pid}_200w.jpg"}


def sealed(pid, name):
    return {"productId": pid, "name": name, "imageUrl": f"https://img.example/{pid}_200w.jpg",
            "extendedData": [{"name": "Description", "value": "Sealed product"}]}


PRODUCTS = {
    1: [
        card(101, "Red's Pikachu - 270/SM-P", "270/SM-P", "Promo"),
        card(102, "Ash's Pikachu - 071/SM-P", "071/SM-P", "Promo"),
        card(103, "Escape Board - 271/SM-P", "271/SM-P", "Promo", "Trainer - Item"),
        card(104, "Basic Grass Energy - 171/SM-P", "171/SM-P", "Promo", "Basic Energy"),
    ],
    2: [
        sealed(201, "Shiny Star V Booster Box"),
        sealed(202, "Shiny Star V Booster Pack"),
        card(203, "Rowlet - 001/190 (Mirror Holofoil)", "001/190", "Common", "Grass"),
        card(204, "Charizard VMAX - 308/190", "308/190", "Shiny Super Rare", "Fire"),
    ],
    3: [
        # Vintage Japanese cards often have no number, but always a type/rarity.
        card(301, "Charizard", None, "Holo Rare", "Fire"),
        card(302, "Double Colorless Energy", None, "Uncommon", "Special Energy"),
        {"productId": 303, "name": "Starter Deck 1996", "extendedData": [], "imageUrl": ""},
    ],
    4: [
        card(401, "Moltres - 007/030", "007/030", "Common", "Fire"),
        card(402, "Charizard VSTAR - 012/030", "012/030", "RRR", "Fire"),
    ],
}


def price(pid, subtype, market):
    return {"productId": pid, "subTypeName": subtype, "lowPrice": market * 0.9,
            "midPrice": market * 1.1, "highPrice": market * 2, "marketPrice": market}


PRICES = {
    1: [price(101, "Holofoil", 454.66)],
    2: [price(201, "Normal", 168.17), price(202, "Normal", 18.38),
        price(204, "Holofoil", 300.0)],
    3: [price(301, "Holofoil", 900.0)],
    4: [],
}


class FixtureTCGCSV(TCGCSV):
    """TCGCSV catalogue that serves the fixtures above instead of the network."""

    prefix = "jp"
    language = "JP"
    category = 85
    filename = "test-catalog.db"

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[str] = []

    async def _get(self, path: str) -> list[dict]:
        self.requests.append(path)
        parts = path.strip("/").split("/")
        if parts == ["groups"]:
            return GROUPS
        group = int(parts[0])
        return PRODUCTS[group] if parts[1] == "products" else PRICES[group]


@pytest.fixture
async def catalog(tmp_path, monkeypatch):
    monkeypatch.setattr("toploader.games.tcgcsv.CACHE_DIR", tmp_path)
    c = FixtureTCGCSV()
    await c.prepare()
    yield c
    await c.close()
