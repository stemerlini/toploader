"""Modal screens: card preview, search & add, entry editor, confirmation."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image as PILImage
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, LoadingIndicator, OptionList, Select, Static
from textual.widgets.option_list import Option
from textual_image._terminal import get_cell_size  # cached probe of the terminal's cell size
from textual_image.renderable import Image as AutoRenderable
from textual_image.renderable.sixel import Image as SixelRenderable
from textual_image.renderable.tgp import Image as TGPRenderable
from textual_image.widget import Image

from .currency import SOURCE_CURRENCY, SYMBOLS, Rates, money
from .db import CONDITION_NAMES, FINISH_NAMES, PRINT_RUNS, Card, Entry
from .games import SOURCE_NAMES, Game, SearchResult
from .images import fetch_image

LANGUAGES = ["JP", "EN", "IT", "FR", "DE", "ES", "PT", "KO", "ZH"]
LANGUAGE_NAMES = {
    "JP": "Japanese", "EN": "English", "IT": "Italian", "FR": "French", "DE": "German",
    "ES": "Spanish", "PT": "Portuguese", "KO": "Korean", "ZH": "Chinese",
}
LANGUAGE_STYLES = {"JP": "bold #ffffff on #bc002d", "EN": "bold #ffffff on #2f5fb3"}


def language_badge(language: str) -> str:
    """Rich markup for a small coloured language tag."""
    style = LANGUAGE_STYLES.get(language, "bold reverse")
    return f"[{style}] {language} [/]"


# -- Preview ------------------------------------------------------------------

# Whether the terminal shows real pixels (Sixel or the kitty protocol). Without
# them a card is a blur of coloured blocks, so on macOS (Apple's Terminal) the
# full image opens in Quick Look instead.
GRAPHICS = AutoRenderable in (SixelRenderable, TGPRenderable)
QUICK_LOOK = sys.platform == "darwin" and not GRAPHICS


def open_externally(path: Path) -> subprocess.Popen | None:
    """Show an image in the system viewer: Quick Look on macOS, else the default app."""
    command = ["qlmanage", "-p", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
    try:
        return subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return None


class PreviewScreen(ModalScreen[bool]):
    """Large card image next to the card's details and prices.

    Shows a card from the collection (`entry`) or straight from the catalogue
    while searching; then Enter adds it and the screen returns True.
    """

    BINDINGS = [
        Binding("space", "dismiss(False)", "Close"),
        Binding("escape", "dismiss(False)", "Close", show=False),
        Binding("q", "dismiss(False)", "Close", show=False),
        Binding("enter", "add", "Add to collection"),
        Binding("o", "open_image", "Open full image"),
    ]

    def __init__(
        self,
        card: Card,
        game: Game,
        source: str,
        currency: str,
        rates: Rates,
        entry: Entry | None = None,
        can_add: bool = False,
    ) -> None:
        super().__init__()
        self.card = card
        self.entry = entry
        self.game = game
        self.source = source
        self.currency = currency
        self.rates = rates
        self.can_add = can_add

    def check_action(self, action: str, parameters) -> bool | None:
        return self.can_add if action == "add" else True

    def action_add(self) -> None:
        self.dismiss(True)

    def action_open_image(self) -> None:
        if self.image_path:
            self.close_viewer()
            self.viewer = open_externally(self.image_path)

    def close_viewer(self) -> None:
        if self.viewer and sys.platform == "darwin":  # Quick Look closes with the preview
            self.viewer.terminate()
        self.viewer = None

    def on_unmount(self) -> None:
        self.close_viewer()

    def compose(self) -> ComposeResult:
        card = self.card
        number = f"  ·  #{card.local_id}" if card.local_id else ""
        with Horizontal(id="preview"):
            with Vertical(id="preview-image"):
                yield LoadingIndicator()
            with VerticalScroll(id="preview-info"):
                yield Static(card.name, classes="title")
                yield Static(f"{card.set_name}{number}", classes="subtitle")
                yield Static(self._details(), classes="details")
                prices = self.game.price_details(card)
                if prices:
                    yield Static("Market prices", classes="section")
                    yield Static(
                        "\n".join(f"[dim]{k:<26}[/] {v}" for k, v in prices), classes="details"
                    )
                updated = card.updated_at[:16].replace("T", " ")
                yield Static(f"[dim]Prices updated {updated} UTC[/]", classes="footnote")
                e = self.entry
                if card.is_sealed and e and e.print_run == "first" and e.my_value is None:
                    yield Static(
                        "[dim]Market data lists one product for every print run, so this is "
                        "most likely the reprint price. Press [b]e[/] in the list to set "
                        "your own value for the first print.[/]",
                        classes="footnote",
                    )
                if self.can_add:
                    yield Static("[b]Enter[/] add to collection · [b]Space[/] back to results",
                                 classes="footnote")

    def _details(self) -> str:
        e, c = self.entry, self.card
        finish = e.finish if e else c.available_finishes[0]
        found = self.game.price(c, finish, self.source)
        price = None
        unit = money(None, self.currency)
        market = ""
        if e and e.my_value is not None:
            # The user's valuation wins; the market price is shown for reference.
            price = self.rates.convert(e.my_value, e.my_value_currency, self.currency)
            unit = f"✎ {money(price, self.currency)}  [dim]your valuation[/]"
            if found:
                native, source = found
                converted = self.rates.convert(native, SOURCE_CURRENCY[source], self.currency)
                market = f"{money(converted, self.currency)}  [dim]{SOURCE_NAMES[source]}[/]"
        elif found:
            native, source = found
            native_currency = SOURCE_CURRENCY[source]
            price = self.rates.convert(native, native_currency, self.currency)
            unit = money(price, self.currency)
            if native_currency != self.currency:
                unit += f"  [dim]≈ {money(native, native_currency)} on {SOURCE_NAMES[source]}[/]"
            else:
                unit += f"  [dim]{SOURCE_NAMES[source]}[/]"
        catalogue = "Japanese" if self.game.card_language(c) == "JP" else "International"
        if c.is_sealed:
            rows = [("Product", c.rarity), ("Catalogue", catalogue)]
        else:
            rows = [
                ("Category", c.category),
                ("Type", ", ".join(c.types)),
                ("Rarity", c.rarity),
                ("Catalogue", catalogue),
            ]
        if not e:
            if not c.is_sealed:
                rows.append(("Finishes", ", ".join(FINISH_NAMES[f] for f in c.available_finishes)))
            rows.append(("Market price", unit))
            return "\n".join(f"[dim]{k:<13}[/] {v}" for k, v in rows if v)

        if c.is_sealed:
            rows.append(("Print", PRINT_RUNS.get(e.print_run, e.print_run)))
        else:
            rows.append(("Finish", FINISH_NAMES.get(e.finish, e.finish)))
        rows += [
            ("Condition", f"{e.condition} — {CONDITION_NAMES.get(e.condition, '')}"),
            ("Language", f"{e.language}  [dim]({LANGUAGE_NAMES.get(e.language, '')})[/]"),
            ("Quantity", str(e.quantity)),
            ("Unit value" if e.my_value is not None else "Unit price", unit),
            ("Market price", market),
            ("Total value", money(price * e.quantity if price else None, self.currency)),
        ]
        if e.purchase_price is not None:
            paid = money(e.purchase_price, e.purchase_currency)
            if e.purchase_currency != self.currency:
                converted = self.rates.convert(e.purchase_price, e.purchase_currency, self.currency)
                paid = f"{money(converted, self.currency)}  [dim]({paid})[/]"
            rows.append(("Paid (each)", paid))
        if e.notes:
            rows.append(("Notes", e.notes))
        return "\n".join(f"[dim]{k:<13}[/] {v}" for k, v in rows if v)

    def on_mount(self) -> None:
        self.image_px: tuple[int, int] | None = None
        self.image_path: Path | None = None
        self.viewer: subprocess.Popen | None = None
        self.load_image()

    @work(exclusive=True)
    async def load_image(self) -> None:
        holder = self.query_one("#preview-image")
        try:
            path = await fetch_image(self.card.image_url)
            with PILImage.open(path) as img:
                self.image_px = img.size
        except Exception:
            path = None
        await holder.remove_children()
        self.image_path = path
        if path and QUICK_LOOK:
            await holder.mount(Static(
                "Full-size image\nopened in Quick Look\n\n[dim]o  open it again[/]",
                classes="no-image"))
            self.action_open_image()
        elif path:
            image = Image(path, id="card-image")
            image.display = False  # shown once it has been sized, to avoid a stretched flash
            await holder.mount(image)
            self.call_after_refresh(self.fit_image)
        else:
            await holder.mount(Static("No image available", classes="no-image"))

    def on_resize(self) -> None:
        self.call_after_refresh(self.fit_image)

    def fit_image(self) -> None:
        """Size the image box so the card keeps its real aspect ratio.

        A terminal cell is not square (often ~7x17 px), so the number of columns
        that matches a given number of rows comes from the cell's pixel size.
        """
        images = self.query("#card-image")
        if not images or not self.image_px:
            return
        image = images.first()
        box = self.query_one("#preview")
        cell = get_cell_size()
        img_w, img_h = self.image_px
        max_rows = max(box.content_size.height, 4)
        max_cols = max(box.content_size.width // 2, 10)  # leave half for the details

        rows = max_rows
        cols = round(rows * cell.height * img_w / (img_h * cell.width))
        if cols > max_cols:
            cols = max_cols
            rows = round(cols * cell.width * img_h / (img_w * cell.height))

        holder = self.query_one("#preview-image")
        holder.styles.width = cols
        image.styles.width = cols
        image.styles.height = rows
        image.display = True

    def on_click(self) -> None:
        self.dismiss(False)


# -- Search & add -------------------------------------------------------------


class SearchScreen(ModalScreen[Card | None]):
    """Search the game's catalogue; returns the chosen card."""

    BINDINGS = [Binding("escape", "dismiss(None)", "Cancel")]

    def __init__(self, game: Game, source: str, currency: str, rates: Rates) -> None:
        super().__init__()
        self.game = game
        self.source = source
        self.currency = currency
        self.rates = rates
        self.results: list[SearchResult] = []
        self.cards: dict[str, Card] = {}  # full card data already downloaded

    def compose(self) -> ComposeResult:
        with Vertical(id="search", classes="dialog"):
            yield Label(f"Add {self.game.name} cards or sealed products", classes="title")
            yield Input(placeholder=self.game.search_hint, id="query")
            yield OptionList(id="results")
            yield Static("Type and press Enter to search · ↓ to pick a result · Esc to cancel",
                         id="search-status", classes="footnote")

    @on(Input.Submitted, "#query")
    def submit(self, event: Input.Submitted) -> None:
        self.run_search(event.value)

    def on_key(self, event) -> None:
        results = self.query_one("#results", OptionList)
        if event.key == "down" and self.focused is self.query_one("#query"):
            results.focus()
            event.stop()
        elif event.key == "space" and self.focused is results:
            if results.highlighted is not None:
                self.preview_card(results.get_option_at_index(results.highlighted).id)
            event.stop()

    @work(exclusive=True)
    async def run_search(self, query: str) -> None:
        status = self.query_one("#search-status", Static)
        results = self.query_one("#results", OptionList)
        try:
            await self.game.prepare(
                lambda done, total: status.update(
                    f"Downloading the {self.game.name} catalogue (first time only)… "
                    f"{done}/{total} sets"
                )
            )
        except Exception as exc:
            status.update(f"[red]Could not download the catalogue:[/] {exc}")
            return
        status.update("Searching…")
        try:
            self.results = await self.game.search(query)
        except Exception as exc:
            status.update(f"[red]Search failed:[/] {exc}")
            return
        results.clear_options()
        results.add_options(
            Option(
                self._result_label(r),
                id=r.id,
            )
            for r in self.results
        )
        status.update(f"{len(self.results)} results · Enter to choose · Space to preview")
        if self.results:
            results.highlighted = 0
            results.focus()

    @staticmethod
    def _result_label(r: SearchResult) -> Text:
        number = f" · #{r.number}" if r.number else ""
        sealed = " [bold reverse] SEALED [/]" if r.sealed else ""
        label = Text.from_markup(
            f"{language_badge(r.language)}{sealed} {r.name}  [dim]{r.set_name}{number}[/]",
            overflow="ellipsis",
        )
        label.no_wrap = True
        return label

    @on(OptionList.OptionSelected, "#results")
    def chosen(self, event: OptionList.OptionSelected) -> None:
        self.load_card(event.option.id)

    async def _get_card(self, card_id: str) -> Card | None:
        if card_id in self.cards:
            return self.cards[card_id]
        status = self.query_one("#search-status", Static)
        status.update("Loading…")
        try:
            card = await self.game.fetch_card(card_id)
        except Exception as exc:
            status.update(f"[red]Could not load it:[/] {exc}")
            return None
        status.update(f"{len(self.results)} results · Enter to choose · Space to preview")
        self.cards[card_id] = card
        return card

    @work(exclusive=True, group="card")
    async def load_card(self, card_id: str) -> None:
        card = await self._get_card(card_id)
        if card:
            self.dismiss(card)

    @work(exclusive=True, group="card")
    async def preview_card(self, card_id: str) -> None:
        card = await self._get_card(card_id)
        if card is None:
            return

        def closed(add: bool | None) -> None:
            if add:
                self.dismiss(card)

        self.app.push_screen(
            PreviewScreen(card, self.game, self.source, self.currency, self.rates, can_add=True),
            closed,
        )


@dataclass
class EntryData:
    finish: str
    condition: str
    language: str
    quantity: int
    purchase_price: float | None
    purchase_currency: str
    notes: str
    print_run: str
    my_value: float | None
    my_value_currency: str


class EntryScreen(ModalScreen[EntryData | None]):
    """Form for finish / condition / language / quantity / price paid."""

    BINDINGS = [Binding("escape", "dismiss(None)", "Cancel")]

    def __init__(
        self, card: Card, entry: Entry | None = None, currency: str = "EUR", language: str = "EN"
    ) -> None:
        super().__init__()
        self.language = language
        self.card = card
        self.entry = entry
        self.currency = currency

    def compose(self) -> ComposeResult:
        e = self.entry
        finishes = self.card.available_finishes
        if e and e.finish not in finishes:
            finishes = [*finishes, e.finish]
        with Vertical(id="entry", classes="dialog"):
            yield Label(("Edit " if e else "Add ") + self.card.name, classes="title")
            details = [self.card.set_name, self.card.local_id and f"#{self.card.local_id}",
                       self.card.rarity]
            yield Static(" · ".join(d for d in details if d), classes="subtitle")
            conditions = self.card.conditions
            if e and e.condition not in conditions:
                conditions = [*conditions, e.condition]
            with Grid(id="entry-form"):
                finish = Select([(FINISH_NAMES[f], f) for f in finishes],
                                value=e.finish if e else finishes[0], allow_blank=False,
                                id="finish", compact=True)
                if not self.card.is_sealed:  # sealed products have no finish
                    yield Label("Finish")
                    yield finish
                yield Label("Condition")
                yield Select([(f"{c} — {CONDITION_NAMES[c]}", c) for c in conditions],
                             value=e.condition if e else ("NM" if "NM" in conditions
                                                           else conditions[0]),
                             allow_blank=False, id="condition", compact=True)
                if self.card.is_sealed:
                    yield Label("Print")
                    yield Select([(name, key) for key, name in PRINT_RUNS.items()],
                                 value=e.print_run if e else "", allow_blank=False,
                                 id="print-run", compact=True)
                yield Label("Language")
                yield Select([(lang, lang) for lang in LANGUAGES],
                             value=e.language if e and e.language in LANGUAGES else self.language,
                             allow_blank=False, id="language", compact=True)
                yield Label("Quantity")
                yield Input(str(e.quantity if e else 1), type="integer", id="quantity",
                            compact=True)
                paid_currency = e.purchase_currency if e and e.purchase_price is not None \
                    else self.currency
                self.paid_currency = paid_currency
                yield Label(f"Paid each ({SYMBOLS.get(paid_currency, paid_currency)})")
                yield Input("" if not e or e.purchase_price is None else f"{e.purchase_price:g}",
                            type="number", placeholder="optional", id="paid", compact=True)
                value_currency = e.my_value_currency if e and e.my_value is not None \
                    else self.currency
                self.value_currency = value_currency
                yield Label(f"Your value ({SYMBOLS.get(value_currency, value_currency)})")
                yield Input("" if not e or e.my_value is None else f"{e.my_value:g}",
                            type="number", id="my-value",
                            placeholder="optional, overrides the market price", compact=True)
                yield Label("Notes")
                yield Input(e.notes if e else "", placeholder="optional", id="notes", compact=True)
            with Horizontal(classes="buttons"):
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#quantity", Input).focus()

    def finish_value(self) -> str:
        selects = self.query("#finish")
        return selects.first(Select).value if selects else self.card.available_finishes[0]

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    @on(Input.Submitted)
    @on(Button.Pressed, "#save")
    def save(self) -> None:
        quantity_text = self.query_one("#quantity", Input).value.strip()
        quantity = int(quantity_text) if quantity_text.lstrip("-").isdigit() else 0
        if quantity < 1:
            self.notify("Quantity must be at least 1", severity="error")
            return
        try:
            paid = self._amount("#paid")
            my_value = self._amount("#my-value")
        except ValueError:
            self.notify("Prices must be numbers", severity="error")
            return
        print_runs = self.query("#print-run")
        self.dismiss(
            EntryData(
                finish=self.finish_value(),
                condition=self.query_one("#condition", Select).value,
                language=self.query_one("#language", Select).value,
                quantity=quantity,
                purchase_price=paid,
                purchase_currency=self.paid_currency if paid is not None else self.currency,
                notes=self.query_one("#notes", Input).value.strip(),
                print_run=print_runs.first(Select).value if print_runs else "",
                my_value=my_value,
                my_value_currency=self.value_currency if my_value is not None else self.currency,
            )
        )

    def _amount(self, selector: str) -> float | None:
        text = self.query_one(selector, Input).value.strip().replace(",", ".")
        return float(text) if text else None


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS = [
        Binding("y", "dismiss(True)", "Yes"),
        Binding("n,escape", "dismiss(False)", "No"),
    ]

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm", classes="dialog"):
            yield Static(self.message)
            with Horizontal(classes="buttons"):
                yield Button("Delete", variant="error", id="yes")
                yield Button("Cancel", id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


# -- About ----------------------------------------------------------------------

KEYS = [
    ("a", "add a card or sealed product"),
    ("space", "preview (also in search results; Enter adds, o full image)"),
    ("e / enter", "edit the selected line"),
    ("+ / -", "change quantity"),
    ("d", "delete"),
    ("g / s", "change grouping / sort"),
    ("/", "filter the list"),
    ("r", "refresh prices"),
    ("c / p", "currency € £ $ / preferred price source"),
    ("q", "quit (and back up to GitHub)"),
]


class AboutScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape,question_mark,space,q", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        from . import __version__, logo
        from .paths import ROOT

        with VerticalScroll(id="about"):
            yield Static(logo.banner(), id="about-banner")
            yield Static(f"[b]Toploader {__version__}[/]  [dim]· your trading card binder in "
                         "the terminal[/]", classes="title")
            yield Static("Search", classes="section")
            yield Static(
                "[dim]by name[/] pikachu · [dim]by number[/] 270/SM-P, swsh3 136 · "
                "[dim]by set[/] s4a, sm10 sealed, sv2a charizard",
                classes="details",
            )
            yield Static("Keys", classes="section")
            yield Static("\n".join(f"[b]{k:<10}[/] {v}" for k, v in KEYS), classes="details")
            yield Static("Data", classes="section")
            yield Static(
                "[dim]Japanese cards & sealed[/] TCGCSV (TCGplayer, daily)\n"
                "[dim]International cards[/]    TCGdex (Cardmarket & TCGplayer)\n"
                "[dim]Exchange rates[/]         ECB via frankfurter.dev\n"
                f"[dim]Collection[/]             {ROOT / 'data' / 'collection.db'}",
                classes="details",
            )
            yield Static("[dim]Esc to close[/]", classes="footnote")
