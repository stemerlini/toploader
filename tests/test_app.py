"""The app driven headless: search & preview, adding, sealed lines, layout."""

import pytest
from PIL import Image as PILImage
from textual.widgets import DataTable, Input, Select

import toploader.app as app_module
import toploader.screens as screens_module
from toploader.app import COLUMNS, Toploader, table_layout
from toploader.currency import Rates
from toploader.db import Card, Database
from toploader.games.base import Game, SearchResult
from toploader.screens import EntryScreen, PreviewScreen, SearchScreen

PIKACHU = Card(id="jp:101", game="pokemon", name="Red's Pikachu", set_id="1",
               set_name="SM-P: Sun & Moon Promos", local_id="270/SM-P", category="Pokemon",
               rarity="Promo", types=["Lightning"], image_url="https://img/101.jpg",
               variants={"holo": True},
               pricing={"usd": 454.66}, updated_at="2099-01-01T00:00:00+00:00")
BOX = Card(id="jp:201", game="pokemon", name="Shiny Star V Booster Box", set_id="2",
           set_name="S4a: Shiny Star V", category="Sealed", rarity="Booster Box",
           image_url="https://img/201.jpg", variants={"normal": True},
           pricing={"usd": 168.17}, updated_at="2099-01-01T00:00:00+00:00")
CARDS = {c.id: c for c in (PIKACHU, BOX)}


class FakeGame(Game):
    id = "pokemon"
    name = "Pokémon"
    icon = "◓"

    async def search(self, query):
        return [SearchResult(c.id, c.name, c.local_id, c.set_id, c.set_name,
                             language="JP", sealed=c.is_sealed) for c in CARDS.values()]

    async def fetch_card(self, card_id):
        return CARDS[card_id]

    async def refresh(self, cards, progress=None):
        return cards

    def price(self, card, finish, preferred):
        return (card.pricing["usd"], "tcgplayer") if "usd" in card.pricing else None

    def card_language(self, card):
        return "JP"


class FixedRates(Rates):
    def __init__(self):
        super().__init__()
        self.rates = {"EUR": 1.0, "USD": 1.1225, "GBP": 0.85033}
        self.date = "2026-10-02"

    @property
    def stale(self):
        return False


@pytest.fixture
def make_app(tmp_path, monkeypatch):
    image = tmp_path / "card.png"
    PILImage.new("RGB", (600, 825), "gold").save(image)

    async def fake_fetch_image(url):
        return image

    monkeypatch.setattr(app_module, "GAMES", [FakeGame])
    monkeypatch.setattr(app_module, "Rates", FixedRates)
    monkeypatch.setattr(screens_module, "fetch_image", fake_fetch_image)
    monkeypatch.setattr("toploader.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr("toploader.config.CONFIG_FILE", tmp_path / "config.json")

    def make():
        return Toploader(Database(tmp_path / "collection.db"))

    return make


async def settle(pilot):
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


async def test_add_from_search_via_preview(make_app):
    app = make_app()
    async with app.run_test(size=(130, 31)) as pilot:
        await pilot.press("a")
        assert isinstance(app.screen, SearchScreen)
        await pilot.press(*"pikachu", "enter")
        await settle(pilot)

        await pilot.press("space")  # preview the highlighted result
        await settle(pilot)
        assert isinstance(app.screen, PreviewScreen) and app.screen.can_add

        await pilot.press("space")  # back to the results
        assert isinstance(app.screen, SearchScreen)

        await pilot.press("space")
        await settle(pilot)
        await pilot.press("enter")  # add from the preview
        await settle(pilot)
        assert isinstance(app.screen, EntryScreen)
        assert app.screen.query_one("#language", Select).value == "JP"

        await pilot.press("enter")  # submit the form
        await settle(pilot)
        [entry] = app.db.entries("pokemon")
        assert (entry.card.id, entry.finish, entry.condition, entry.quantity) == \
               ("jp:101", "holo", "NM", 1)
        assert app.query_one("#cards", DataTable).row_count == 1
        assert app.price_of(entry) == pytest.approx(405.04, abs=0.01)  # $454.66 in €


async def test_sealed_form_print_run_and_own_value(make_app):
    app = make_app()
    app.db.add_entry(BOX, "normal", "S", "JP", 1)
    async with app.run_test(size=(130, 31)) as pilot:
        await settle(pilot)
        await pilot.press("e")
        form = app.screen
        assert isinstance(form, EntryScreen)
        assert not form.query("#finish")  # sealed products have no finish
        assert form.query_one("#condition", Select).value == "S"

        form.query_one("#print-run", Select).value = "first"
        form.query_one("#my-value", Input).value = "420"
        form.save()
        await settle(pilot)

        [entry] = app.db.entries("pokemon")
        assert (entry.print_run, entry.my_value, entry.my_value_currency) == \
               ("first", 420.0, "EUR")
        assert app.price_of(entry) == 420.0
        table = app.query_one("#cards", DataTable)
        assert str(table.get_cell_at((0, list(app._layout).index("price")))).startswith("✎")


async def test_preview_keeps_the_card_aspect_ratio(make_app):
    app = make_app()
    app.db.add_entry(PIKACHU, "holo", "NM", "JP", 1)
    for size in [(130, 31), (200, 55), (90, 45)]:
        async with app.run_test(size=size) as pilot:
            await settle(pilot)
            await pilot.press("space")
            await settle(pilot)
            await pilot.pause()
            image = app.screen.query_one("#card-image")
            cols, rows = image.size.width, image.size.height
            # 7x17 px cells (see conftest); one cell of rounding at most.
            assert cols * 7 / (rows * 17) == pytest.approx(600 / 825, rel=0.05), size
            app = make_app()


async def test_currency_cycles_and_is_remembered(make_app):
    app = make_app()
    app.db.add_entry(PIKACHU, "holo", "NM", "JP", 1)
    async with app.run_test(size=(130, 31)) as pilot:
        await settle(pilot)
        [entry] = app.entries
        await pilot.press("c")
        assert app.currency == "GBP"
        assert app.price_of(entry) == pytest.approx(344.42, abs=0.01)
    assert make_app().config.currency == "GBP"


@pytest.mark.parametrize("width", range(50, 221, 10))
def test_table_layout_fits(width):
    layout = table_layout(width)
    assert {"name", "price", "value", "qty", "condition"} <= set(layout)
    used = sum(layout.values()) + 2 * len(layout)
    if width >= 70:
        assert used <= width


def test_table_layout_drops_set_first_and_keeps_everything_when_wide():
    assert "set" not in table_layout(110) and "rarity" in table_layout(115)
    assert set(table_layout(200)) == {key for key, *_ in COLUMNS}


async def test_about_screen(make_app):
    from toploader import __version__
    from toploader.screens import AboutScreen

    app = make_app()
    async with app.run_test(size=(130, 31)) as pilot:
        await pilot.press("question_mark")
        assert isinstance(app.screen, AboutScreen)
        assert __version__ in str(app.screen.query_one(".title").render())
        await pilot.press("escape")
        assert not isinstance(app.screen, AboutScreen)
