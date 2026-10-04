"""Price rules: TCGdex finish mapping, the combined Pokémon game, currencies."""

import pytest

from toploader.currency import Rates, money
from toploader.db import Card
from toploader.games.base import Catalog, SearchResult
from toploader.games.pokemon import Pokemon
from toploader.games.tcgdex import TCGdex

# -- TCGdex -----------------------------------------------------------------------

BASE_CHARIZARD = Card(
    id="base1-4", game="", name="Charizard",
    variants={"holo": True, "firstEdition": True},
    pricing={
        "cardmarket": {"trend": 636.35, "avg": 741.93, "trend-holo": 123.63, "avg-holo": 130.0},
        "tcgplayer": {"holofoil": {"marketPrice": 944.53},
                      "1stEditionHolofoil": {"marketPrice": 5000.0}},
    },
)


@pytest.fixture
async def tcgdex():
    c = TCGdex()
    yield c
    await c.close()


def test_cardmarket_holo_uses_the_plain_trend(tcgdex):
    # Cardmarket's "-holo" fields are the reverse holo, not the holo card.
    assert tcgdex.price(BASE_CHARIZARD, "holo", "cardmarket") == 636.35


def test_cardmarket_reverse_uses_the_holo_fields(tcgdex):
    assert tcgdex.price(BASE_CHARIZARD, "reverse", "cardmarket") == 123.63


def test_tcgplayer_finish_mapping(tcgdex):
    assert tcgdex.price(BASE_CHARIZARD, "holo", "tcgplayer") == 944.53
    assert tcgdex.price(BASE_CHARIZARD, "firstEdition", "tcgplayer") == 5000.0


def test_missing_prices(tcgdex):
    assert tcgdex.price(Card(id="x", game="", name="x"), "normal", "cardmarket") is None


# -- the combined Pokémon game ---------------------------------------------------------


class FakeCatalog(Catalog):
    def __init__(self, prefix, language, sources, results=0, fail=False, value=10.0):
        self.prefix, self.language, self.sources = prefix, language, sources
        self.results, self.fail, self.value = results, fail, value

    async def search(self, query):
        if self.fail:
            raise RuntimeError(f"{self.prefix} is down")
        return [SearchResult(str(i), "Card", "", "s", "Set") for i in range(self.results)]

    async def fetch_card(self, card_id):
        return Card(id=card_id, game="", name="Card")

    async def refresh(self, cards, progress=None):
        return [Card(id=c.id, game="", name="Fresh") for c in cards]

    def price(self, card, finish, source):
        return self.value if source in self.sources else None


@pytest.fixture
async def pokemon():
    game = Pokemon()
    for c in game.catalogs.values():
        await c.close()
    yield game


def use(game, *catalogs):
    game.catalogs = {c.prefix: c for c in catalogs}


async def test_search_prefixes_ids_and_sets_language(pokemon):
    use(pokemon, FakeCatalog("jp", "JP", ["tcgplayer"], 1), FakeCatalog("en", "EN", [], 1))
    results = await pokemon.search("x")
    assert [(r.id, r.language) for r in results] == [("jp:0", "JP"), ("en:0", "EN")]


async def test_results_are_capped_only_when_several_catalogues_answer(pokemon):
    use(pokemon, FakeCatalog("jp", "JP", [], 400), FakeCatalog("en", "EN", [], 400))
    assert len(await pokemon.search("x")) == 2 * Pokemon.MAX_PER_CATALOG

    use(pokemon, FakeCatalog("jp", "JP", [], 400), FakeCatalog("en", "EN", [], 0))
    assert len(await pokemon.search("s4a")) == 400  # browsing one set shows all of it


async def test_one_catalogue_failing_does_not_break_search(pokemon):
    use(pokemon, FakeCatalog("jp", "JP", [], 2), FakeCatalog("en", "EN", [], fail=True))
    assert len(await pokemon.search("x")) == 2

    use(pokemon, FakeCatalog("jp", "JP", [], fail=True), FakeCatalog("en", "EN", [], fail=True))
    with pytest.raises(RuntimeError):
        await pokemon.search("x")


async def test_fetch_and_refresh_keep_prefixed_ids(pokemon):
    use(pokemon, FakeCatalog("jp", "JP", []), FakeCatalog("en", "EN", []))
    card = await pokemon.fetch_card("jp:598347")
    assert (card.id, card.game) == ("jp:598347", "pokemon")
    fresh = await pokemon.refresh([card, Card(id="en:base1-4", game="pokemon", name="x")])
    assert sorted(c.id for c in fresh) == ["en:base1-4", "jp:598347"]
    assert all(c.name == "Fresh" for c in fresh)


def test_price_prefers_the_chosen_source_and_falls_back(pokemon):
    use(pokemon, FakeCatalog("jp", "JP", ["tcgplayer"], value=5.0),
        FakeCatalog("en", "EN", ["cardmarket", "tcgplayer"], value=7.0))
    jp = Card(id="jp:1", game="pokemon", name="x")
    en = Card(id="en:1", game="pokemon", name="x")
    # Japanese cards only have TCGplayer prices, whatever the preference.
    assert pokemon.price(jp, "normal", "cardmarket") == (5.0, "tcgplayer")
    assert pokemon.price(en, "normal", "cardmarket") == (7.0, "cardmarket")
    assert pokemon.price(en, "normal", "tcgplayer") == (7.0, "tcgplayer")


def test_card_language_comes_from_the_catalogue(pokemon):
    use(pokemon, FakeCatalog("jp", "JP", []), FakeCatalog("ens", "EN", []))
    assert pokemon.card_language(Card(id="jp:1", game="", name="x")) == "JP"
    assert pokemon.card_language(Card(id="ens:1", game="", name="x")) == "EN"


# -- currencies -------------------------------------------------------------------------


@pytest.fixture
def rates():
    r = Rates()
    r.rates = {"EUR": 1.0, "USD": 1.1225, "GBP": 0.85033}
    return r


def test_convert(rates):
    assert rates.convert(454.66, "USD", "EUR") == pytest.approx(405.04, abs=0.01)
    assert rates.convert(405.04, "EUR", "GBP") == pytest.approx(344.42, abs=0.01)
    assert rates.convert(10.0, "EUR", "EUR") == 10.0
    assert rates.convert(None, "USD", "EUR") is None


def test_convert_without_a_rate(rates):
    assert rates.convert(10.0, "JPY", "EUR") is None


def test_money():
    assert money(1234.5, "EUR") == "€1,234.50"
    assert money(3.0, "GBP") == "£3.00"
    assert money(None, "USD") == "—"
