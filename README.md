# Toploader

A terminal app for tracking a trading card collection. It supports Pokémon for now,
and other games can plug in later as new tabs.

- Cards are grouped in a sidebar by set, language, type, rarity, category or condition.
- **Space** opens a preview with the card image (Sixel in foot, otherwise unicode
  half-blocks), card details and market prices — in the collection and in search
  results (where Enter adds the previewed card).
- **Sealed products** (booster boxes, packs, ETBs, promo packs, collection boxes…) are
  tracked next to singles, Japanese and international. They show a ◆ marker and a
  SEALED tag in search, use the conditions Sealed / Sealed with damaged packaging /
  Opened, and are priced from TCGplayer.
- **Print run** (sealed): Unknown / First print / Reprint. A first-print box and a
  reprint box are separate lines. TCGplayer lists one product for every print run, so
  its price is usually the reprint price.
- **Your value**: an optional per-line valuation that replaces the market price in all
  totals, marked ✎ in the list. Useful for first prints, graded cards or anything the
  market data can't tell apart.
- The list adapts to the window width: on narrow terminals the Set, Rarity and #
  columns are hidden (in that order) before anything gets cut off.
- **Japanese and English cards live together.** One search covers both catalogues, and
  each card carries a language flag (JP / EN / IT …) shown as a coloured badge. Group the
  sidebar by language (`g`) to see them separately.
  - Japanese printings come from [TCGCSV](https://tcgcsv.com), a free daily mirror of
    TCGplayer's "Pokemon Japan" catalogue: every set and promo, with English card names,
    images and USD prices. The card list (~28k cards, 4 MB) downloads on the first search
    and refreshes weekly.
  - International printings come from [TCGdex](https://tcgdex.dev): Cardmarket (EUR) and
    TCGplayer (USD) prices.
  - International sealed products come from TCGCSV's "Pokemon" category.
  - Search by English name or number: `270/SM-P`, `SM-P 270`, `swsh3 136`,
    `151 booster box`.
  - Search by set code to browse an expansion: `s4a` lists the whole set (sealed
    products first), `s4a sealed` or `sm10 sealed` only its sealed products, and
    `sm10a box` narrows within it. `sealed` on its own lists sealed products.
- `p` picks the preferred price source; cards it doesn't cover (Japanese cards have
  no Cardmarket price here) fall back to the other one, and the top bar shows which
  sources are in use.
- All prices are shown in euros by default (`c` cycles € / £ / $). TCGplayer's dollar
  prices are converted with the daily ECB exchange rate from frankfurter.dev.
- Prices refresh automatically on start when older than 24 h, or on demand with `r`.
- Inventory is tracked per finish (normal / holo / reverse / 1st edition), condition
  (Cardmarket scale M → PO), language, quantity, price paid and notes.
- Colours follow the active Omarchy theme.

## Run

```sh
python3 -m venv .venv && .venv/bin/pip install -e .
./toploader
```

## Tests

```sh
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

The tests run offline: the price sources are replaced by small fixtures shaped like
the real TCGCSV/TCGdex data, and the app is driven headless (search and preview,
adding cards, sealed products, the preview's aspect ratio, table layout, currencies,
and migrations of older collection files).

## Keys

| Key | Action |
|---|---|
| `a` | Add a card (search by name, or by set id + number such as `swsh3 136`) |
| `space` | Preview the card image and details |
| `e` / `enter` | Edit the selected line |
| `+` / `-` | Change quantity |
| `d` | Delete |
| `g` | Cycle grouping |
| `s` | Cycle sort (set, name, value, quantity) |
| `/` | Filter (`esc` clears) |
| `r` | Refresh prices |
| `c` | Show prices in € / £ / $ (converted with daily ECB rates) |
| `p` | Prefer Cardmarket or TCGplayer prices |
| `tab` | Switch between sidebar and list |
| `q` | Quit |

## Files

Everything stays inside this folder:

- `data/collection.db`: your collection (SQLite)
- `data/config.json`: settings (grouping, sort, price source)
- `cache/images/`: downloaded card images, safe to delete
- `cache/tcgcsv-*.db`: downloaded product lists (Japanese, international sealed), safe to delete

Set `TOPLOADER_HOME=/some/path` to keep the data somewhere else.

**Automatic backup:** when you quit, Toploader commits `data/collection.db` and
`data/config.json` (only those files) with a summary such as "Collection: 52 cards
(23 unique), €3,297.29" and pushes to GitHub. Offline, the commit stays local and is
pushed next time. Turn it off with `"auto_backup": false` in `data/config.json`.

## Adding another game

Subclass `games.base.Game` (search, fetch_card, refresh, price) and add it to
`GAMES` in `games/__init__.py`. It then appears as a tab in the top bar.
