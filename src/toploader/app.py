"""Main application: game tabs, category sidebar, card table."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC
from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Input, OptionList, Static, Tab, Tabs
from textual.widgets.option_list import Option

from . import logo
from .config import Config
from .currency import CURRENCIES, SOURCE_CURRENCY, SYMBOLS, Rates, money
from .db import FINISH_NAMES, Card, Database, Entry
from .games import GAMES, SOURCE_NAMES, Game
from .screens import (
    LANGUAGE_NAMES,
    LANGUAGE_STYLES,
    AboutScreen,
    ConfirmScreen,
    EntryData,
    EntryScreen,
    PreviewScreen,
    SearchScreen,
)
from .theme import omarchy_theme

GROUPINGS = ["set", "language", "type", "rarity", "category", "condition"]
SORTS = ["set", "name", "value", "quantity"]
ALL = "__all__"

TYPE_COLORS = {
    "Grass": "#78c850", "Fire": "#f08030", "Water": "#6890f0", "Lightning": "#f8d030",
    "Psychic": "#f85888", "Fighting": "#c03028", "Darkness": "#705848", "Metal": "#b8b8d0",
    "Fairy": "#ee99ac", "Dragon": "#7038f8", "Colorless": "#a8a878",
}

RARITY_SHORT = {
    "Special illustration rare": "Special Illus.",
    "Illustration rare": "Illustration",
    "Hyper rare": "Hyper Rare",
    "Double rare": "Double Rare",
    "Ultra Rare": "Ultra Rare",
    "Secret Rare": "Secret Rare",
    "Rare Holo": "Rare Holo",
    "Holo Rare V": "Holo V",
    "Holo Rare VMAX": "Holo VMAX",
    "Holo Rare VSTAR": "Holo VSTAR",
    "Shiny rare": "Shiny",
    "ACE SPEC Rare": "ACE SPEC",
}


# Table columns: (key, header, width, drop order). Width None = shares the
# leftover space. When the window is narrow, columns with the highest drop
# order are hidden first; 0 means always shown.
COLUMNS = [
    ("language", "Lang", 4, 0),
    ("name", "Name", None, 0),
    ("number", "#", 9, 2),
    ("set", "Set", None, 4),
    ("rarity", "Rarity", 14, 3),
    ("finish", "Finish", 12, 1),
    ("condition", "Cond.", 5, 0),
    ("qty", "Qty", 3, 0),
    ("price", "Price", 10, 0),
    ("value", "Value", 10, 0),
]
NAME_MIN, SET_MIN = 18, 14
RIGHT_ALIGNED = {"qty", "price", "value"}


def table_layout(width: int) -> dict[str, int]:
    """Column key → width that fits `width` cells, dropping columns if needed."""
    columns = list(COLUMNS)
    while True:
        fixed = sum(w for _, _, w, _ in columns if w) + 2 * len(columns)  # 2 = cell padding
        flexible = [k for k, _, w, _ in columns if w is None]
        minimum = NAME_MIN + (SET_MIN if "set" in flexible else 0)
        droppable = [c for c in columns if c[3]]
        if fixed + minimum <= width or not droppable:
            break
        columns.remove(max(droppable, key=lambda c: c[3]))
    spare = max(width - fixed, NAME_MIN)
    if "set" in flexible:  # Name gets 60% of the spare room, Set the rest
        name_w = max(NAME_MIN, spare * 3 // 5)
        flex = {"name": name_w, "set": max(SET_MIN, spare - name_w)}
    else:
        flex = {"name": spare}
    return {k: (w if w else flex[k]) for k, _, w, _ in columns}


SEALED_LABELS = {"": "sealed", "first": "1st print", "reprint": "reprint"}


def clip(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def group_key(entry: Entry, grouping: str) -> str:
    card = entry.card
    if grouping == "set":
        return card.set_name or "Unknown set"
    if grouping == "type":
        if card.types:
            return card.types[0]
        return card.category or "Other"
    if grouping == "rarity":
        return card.rarity or "Unknown rarity"
    if grouping == "category":
        return card.category or "Other"
    if grouping == "condition":
        return entry.condition
    if grouping == "language":
        return LANGUAGE_NAMES.get(entry.language, entry.language)
    return ""


class Toploader(App):
    TITLE = "Toploader"
    CSS_PATH = Path(__file__).with_name("app.tcss")

    BINDINGS = [
        Binding("space", "preview", "Preview"),
        Binding("a", "add", "Add"),
        Binding("e", "edit", "Edit"),
        Binding("plus,equals_sign", "change_qty(1)", "+1", key_display="+"),
        Binding("minus", "change_qty(-1)", "−1", key_display="-"),
        Binding("d,delete", "delete", "Delete"),
        Binding("g", "cycle_group", "Group"),
        Binding("s", "cycle_sort", "Sort"),
        Binding("slash", "filter", "Filter", key_display="/"),
        Binding("r", "refresh_prices", "Refresh prices"),
        Binding("c", "cycle_currency", "€/£/$"),
        Binding("p", "toggle_source", "Price source"),
        Binding("tab", "focus_next", "Switch pane", show=False),
        Binding("question_mark", "about", "About", key_display="?"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, db: Database | None = None) -> None:
        super().__init__()
        self.db = db or Database()
        self.config = Config.load()
        self.rates = Rates()
        self.games: dict[str, Game] = {g.id: g() for g in GAMES}
        self.game: Game = self.games.get(self.config.game) or next(iter(self.games.values()))
        self.entries: list[Entry] = []
        self.group: str = ALL
        self.filter_text = ""

    # -- layout ------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Horizontal(id="topbar"):
            yield Static(logo.to_text(logo.sprite(logo.SMALL_BALL)), id="brand-logo")
            with Vertical(id="brand"):
                yield Static("Toploader", id="brand-name")
                yield Static("card collection", id="brand-tagline")
            yield Tabs(*(Tab(f"{g.icon} {g.name}", id=g.id) for g in self.games.values()),
                       id="games")
            yield Static(id="stats")
        with Horizontal(id="body"):
            with Vertical(id="sidebar"):
                yield Static(id="group-title", classes="pane-title")
                yield OptionList(id="groups")
            with Vertical(id="main"):
                yield Static(id="list-title", classes="pane-title")
                yield Input(placeholder="Filter by name, set, rarity…  (Esc to clear)",
                            id="filter")
                yield DataTable(id="cards", cursor_type="row", zebra_stripes=True)
                yield Static(id="empty")
        yield Footer()

    def on_mount(self) -> None:
        theme = omarchy_theme()
        if theme:
            self.register_theme(theme)
            self.theme = theme.name
        table = self.query_one("#cards", DataTable)
        self.query_one("#filter").display = False
        self.query_one("#games", Tabs).active = self.game.id
        self.reload()
        table.focus()

    async def on_unmount(self) -> None:
        for game in self.games.values():
            await game.close()

    # -- data → widgets ----------------------------------------------------

    @property
    def source(self) -> str:
        """Preferred price source; cards it doesn't cover use another one."""
        return self.config.price_source if self.config.price_source in SOURCE_NAMES \
            else "cardmarket"

    @property
    def currency(self) -> str:
        return self.config.currency if self.config.currency in CURRENCIES else "EUR"

    def price_of(self, entry: Entry) -> float | None:
        """Unit value in the display currency: the user's own valuation if set,
        otherwise the market price."""
        if entry.my_value is not None:
            return self.rates.convert(entry.my_value, entry.my_value_currency, self.currency)
        found = self.game.price(entry.card, entry.finish, self.source)
        if found is None:
            return None
        native, source = found
        return self.rates.convert(native, SOURCE_CURRENCY[source], self.currency)

    def source_of(self, entry: Entry) -> str | None:
        if entry.my_value is not None:
            return None
        found = self.game.price(entry.card, entry.finish, self.source)
        return found[1] if found else None

    def reload(self, keep_entry: int | None = None) -> None:
        self.entries = self.db.entries(self.game.id)
        self.refresh_stats()
        self.refresh_groups()
        self.refresh_table(keep_entry)

    def summary(self) -> tuple[int, int, float]:
        """(copies, unique cards, total value in the display currency)."""
        copies = sum(e.quantity for e in self.entries)
        unique = len({e.card.id for e in self.entries})
        value = sum((self.price_of(e) or 0) * e.quantity for e in self.entries)
        return copies, unique, value

    def refresh_stats(self) -> None:
        currency = self.currency
        used = {self.source_of(e) for e in self.entries} - {None} or {self.source}
        # Preferred source first, e.g. "Cardmarket + TCGplayer → €".
        sources = " + ".join(SOURCE_NAMES[s] for s in sorted(used, key=lambda s: s != self.source))
        converted = any(SOURCE_CURRENCY[s] != currency for s in used)
        copies, unique, value = self.summary()
        self.query_one("#stats", Static).update(
            f"[b]{copies}[/] cards · [b]{unique}[/] unique · "
            f"[b $success]{money(value, currency)}[/] [dim]{sources}"
            + (" → " + SYMBOLS[currency] if converted else "")
            + "[/]"
        )

    def refresh_groups(self) -> None:
        grouping = self.config.group_by
        self.query_one("#group-title", Static).update(
            f"BY {grouping.upper()}  [dim]g to change[/]"
        )
        counts: dict[str, int] = defaultdict(int)
        values: dict[str, float] = defaultdict(float)
        for e in self.entries:
            key = group_key(e, grouping)
            counts[key] += e.quantity
            values[key] += (self.price_of(e) or 0) * e.quantity

        def label(name: str, count: int, value: float) -> Text:
            text = Text(overflow="ellipsis", no_wrap=True)
            if grouping == "type" and name in TYPE_COLORS:
                text.append("● ", style=TYPE_COLORS[name])
            if grouping == "language":
                code = next((k for k, v in LANGUAGE_NAMES.items() if v == name), "")
                if code:
                    text.append(f" {code} ", style=LANGUAGE_STYLES.get(code, "bold reverse"))
                    text.append(" ")
            text.append(name)
            text.append(f"\n  {count} · {money(value, self.currency)}", style="dim")
            return text

        groups = self.query_one("#groups", OptionList)
        groups.clear_options()
        total = sum(counts.values())
        groups.add_option(Option(label("All cards", total, sum(values.values())), id=ALL))
        for name in sorted(counts, key=str.casefold):
            groups.add_option(Option(label(name, counts[name], values[name]), id=name))
        if self.group != ALL and self.group not in counts:
            self.group = ALL
        groups.highlighted = groups.get_option_index(self.group)

    def visible_entries(self) -> list[Entry]:
        entries = [
            e for e in self.entries
            if self.group == ALL or group_key(e, self.config.group_by) == self.group
        ]
        if self.filter_text:
            needle = self.filter_text.casefold()
            entries = [
                e for e in entries
                if needle in " ".join(
                    [e.card.name, e.card.set_name, e.card.rarity, e.card.local_id,
                     e.card.category,
                     e.condition, e.notes, e.language,
                     LANGUAGE_NAMES.get(e.language, ""), *e.card.types]
                ).casefold()
            ]
        sort = self.config.sort_by
        if sort == "name":
            entries.sort(key=lambda e: e.card.name.casefold())
        elif sort == "value":
            entries.sort(key=lambda e: (self.price_of(e) or 0) * e.quantity, reverse=True)
        elif sort == "quantity":
            entries.sort(key=lambda e: e.quantity, reverse=True)
        return entries

    def on_resize(self) -> None:
        self.call_after_refresh(self.refresh_table)

    def refresh_table(self, keep_entry: int | None = None) -> None:
        table = self.query_one("#cards", DataTable)
        if keep_entry is None and table.row_count:
            keep_entry = self.current_entry_id()
        old_row = table.cursor_row

        # Leave 2 cells for the vertical scrollbar.
        main_width = self.query_one("#main").content_size.width or self.size.width - 34
        layout = table_layout(main_width - 2)
        if layout != getattr(self, "_layout", None):
            self._layout = layout
            table.clear(columns=True)
            headers = {k: h for k, h, _, _ in COLUMNS}
            for key, width in layout.items():
                header = Text(headers[key], justify="right" if key in RIGHT_ALIGNED else "left")
                table.add_column(header, key=key, width=width)
        else:
            table.clear()

        currency = self.currency
        visible = self.visible_entries()
        for e in visible:
            price = self.price_of(e)
            name = Text(clip(e.card.name, layout["name"] - 2), style="bold")
            if e.card.is_sealed:
                name = Text.assemble(("◆ ", "bold magenta"), name)
            elif e.card.types and e.card.types[0] in TYPE_COLORS:
                name = Text.assemble(("● ", TYPE_COLORS[e.card.types[0]]), name)
            else:
                name = Text.assemble("  ", name)
            language = Text(f" {e.language} ",
                            style=LANGUAGE_STYLES.get(e.language, "bold reverse"))
            cells = {
                "language": language,
                "name": name,
                "number": clip(e.card.local_id, layout.get("number", 9)),
                "set": Text(clip(e.card.set_name, layout.get("set", 20)), style="dim"),
                "rarity": clip(RARITY_SHORT.get(e.card.rarity, e.card.rarity), 14),
                "finish": Text(SEALED_LABELS.get(e.print_run, "sealed"),
                               style="bold" if e.print_run == "first" else "dim italic")
                if e.card.is_sealed else FINISH_NAMES.get(e.finish, e.finish),
                "condition": e.condition,
                "qty": Text(str(e.quantity), justify="right"),
                # ✎ marks the user's own valuation instead of a market price.
                "price": Text(("✎" if e.my_value is not None else "") + money(price, currency),
                              justify="right"),
                "value": Text(money(price * e.quantity if price else None, currency),
                              justify="right", style="green"),
            }
            table.add_row(*(cells[k] for k in layout), key=str(e.id))
        if keep_entry is not None and any(e.id == keep_entry for e in visible):
            table.move_cursor(row=table.get_row_index(str(keep_entry)))
        elif visible:
            table.move_cursor(row=min(old_row, len(visible) - 1))

        group = "All cards" if self.group == ALL else self.group
        flt = f'  [dim]filter:[/] "{self.filter_text}"' if self.filter_text else ""
        self.query_one("#list-title", Static).update(
            f"{group.upper()}  [dim]{len(visible)} lines · sorted by {self.config.sort_by}[/]{flt}"
        )
        empty = self.query_one("#empty", Static)
        empty.display = not visible
        table.display = bool(visible)
        if not self.entries:
            empty.update(Text.assemble(
                logo.banner(), "\n\n\nYour binder is empty.\n\nPress ",
                ("a", "bold"), " to add your first card or sealed product.",
            ))
        else:
            empty.update("No cards match.")

    def current_entry_id(self) -> int | None:
        table = self.query_one("#cards", DataTable)
        if not table.row_count:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        return int(row_key.value)

    def current_entry(self) -> Entry | None:
        entry_id = self.current_entry_id()
        return next((e for e in self.entries if e.id == entry_id), None)

    # -- events ------------------------------------------------------------

    @on(OptionList.OptionHighlighted, "#groups")
    def group_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option.id != self.group:
            self.group = event.option.id
            self.refresh_table()

    @on(OptionList.OptionSelected, "#groups")
    def group_selected(self) -> None:
        self.query_one("#cards").focus()

    @on(Tabs.TabActivated, "#games")
    def game_changed(self, event: Tabs.TabActivated) -> None:
        game = self.games.get(event.tab.id)
        if game and game is not self.game:
            self.game = game
            self.group = ALL
            self.config.game = game.id
            self.config.save()
            self.reload()

    @on(DataTable.RowSelected, "#cards")
    def row_selected(self) -> None:
        self.action_edit()

    @on(Input.Changed, "#filter")
    def filter_changed(self, event: Input.Changed) -> None:
        self.filter_text = event.value.strip()
        self.refresh_table()

    @on(Input.Submitted, "#filter")
    def filter_submitted(self) -> None:
        self.query_one("#cards").focus()

    def on_key(self, event) -> None:
        flt = self.query_one("#filter", Input)
        if event.key == "escape" and flt.display:
            flt.value = ""
            flt.display = False
            self.query_one("#cards").focus()
            event.stop()

    # -- actions -----------------------------------------------------------

    def action_about(self) -> None:
        self.push_screen(AboutScreen())

    def action_preview(self) -> None:
        entry = self.current_entry()
        if entry:
            self.push_screen(
                PreviewScreen(entry.card, self.game, self.source, self.currency, self.rates,
                              entry=entry)
            )

    def action_add(self) -> None:
        def card_chosen(card: Card | None) -> None:
            if card is None:
                return

            def saved(data: EntryData | None) -> None:
                if data is None:
                    return
                entry_id = self.db.add_entry(card, **vars(data))
                self.group = ALL
                self.reload(keep_entry=entry_id)
                self.notify(f"Added {data.quantity}× {card.name}")

            self.push_screen(
                EntryScreen(card, currency=self.currency, language=self.game.card_language(card)),
                saved,
            )

        self.push_screen(SearchScreen(self.game, self.source, self.currency, self.rates),
                         card_chosen)

    def action_edit(self) -> None:
        entry = self.current_entry()
        if not entry:
            return

        def saved(data: EntryData | None) -> None:
            if data is not None:
                self.db.update_entry(entry.id, **vars(data))
                self.reload(keep_entry=entry.id)

        self.push_screen(
            EntryScreen(entry.card, entry, currency=self.currency), saved
        )

    def action_change_qty(self, delta: int) -> None:
        entry = self.current_entry()
        if not entry:
            return
        if entry.quantity + delta < 1:
            self.action_delete()
            return
        self.db.update_entry(entry.id, quantity=entry.quantity + delta)
        self.reload(keep_entry=entry.id)

    def action_delete(self) -> None:
        entry = self.current_entry()
        if not entry:
            return

        def confirmed(yes: bool | None) -> None:
            if yes:
                self.db.delete_entry(entry.id)
                self.reload()
                self.notify(f"Removed {entry.card.name}")

        self.push_screen(
            ConfirmScreen(
                f"Remove [b]{entry.card.name}[/] ({FINISH_NAMES.get(entry.finish)}, "
                f"{entry.condition}, ×{entry.quantity}) from your binder?"
            ),
            confirmed,
        )

    def action_cycle_group(self) -> None:
        i = GROUPINGS.index(self.config.group_by)
        self.config.group_by = GROUPINGS[(i + 1) % len(GROUPINGS)]
        self.config.save()
        self.group = ALL
        self.refresh_groups()
        self.refresh_table()

    def action_cycle_sort(self) -> None:
        i = SORTS.index(self.config.sort_by)
        self.config.sort_by = SORTS[(i + 1) % len(SORTS)]
        self.config.save()
        self.refresh_table()

    def action_cycle_currency(self) -> None:
        i = CURRENCIES.index(self.currency)
        self.config.currency = CURRENCIES[(i + 1) % len(CURRENCIES)]
        self.config.save()
        self.reload()
        self.notify(f"Showing prices in {self.currency} ({SYMBOLS[self.currency]})")

    @work(exclusive=True, group="rates")
    async def update_rates(self) -> None:
        if not self.rates.stale:
            return
        try:
            await self.rates.update()
        except Exception:
            if self.rates.fetched_at is None:
                self.notify("Could not download exchange rates; converted prices show —",
                            severity="warning")
            return
        self.reload()

    def action_toggle_source(self) -> None:
        self.config.price_source = (
            "tcgplayer" if self.config.price_source == "cardmarket" else "cardmarket"
        )
        self.config.save()
        self.reload()
        self.notify(f"Preferring {SOURCE_NAMES[self.source]} prices "
                    "(cards it doesn't list fall back to the other source)")

    def action_filter(self) -> None:
        flt = self.query_one("#filter", Input)
        flt.display = True
        flt.focus()

    @work(exclusive=True, group="prices")
    async def action_refresh_prices(self) -> None:
        cards = {e.card.id: e.card for e in self.entries}
        if not cards:
            return
        self.notify(f"Updating prices for {len(cards)} cards…")
        fresh = await self.game.refresh(list(cards.values()))
        for card in fresh:
            self.db.upsert_card(card)
        self.reload()
        self.notify("Prices updated", severity="information")

    @work(exclusive=True, group="prices")
    async def refresh_if_stale(self) -> None:
        """Refresh prices on startup when they are older than a day."""
        from datetime import datetime, timedelta

        cutoff = datetime.now(UTC) - timedelta(hours=24)
        stale = [
            e.card for e in self.entries
            if not e.card.updated_at or datetime.fromisoformat(e.card.updated_at) < cutoff
        ]
        if not stale:
            return
        unique = list({c.id: c for c in stale}.values())
        fresh = await self.game.refresh(unique)
        for card in fresh:
            self.db.upsert_card(card)
        self.reload()
        self.notify(f"Prices updated for {len(unique)} cards")

    def on_ready(self) -> None:
        self.update_rates()
        self.refresh_if_stale()
