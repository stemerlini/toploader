# Changelog

## 1.2.0 — 2026-10-07

### macOS
- Standalone executable for Apple Silicon and Intel Macs, built on GitHub and attached
  to each release (`toploader-…-macos-apple-silicon.zip`, `…-intel.zip`); install notes
  in `packaging/MAC.md`.
- A standalone or installed copy keeps its collection in the platform data folder
  (`~/Library/Application Support/Toploader` on macOS); running from the project folder
  is unchanged. The backup on quit only runs when the data folder is a git repository.

## 1.1.0 — 2026-10-04

### Omarchy integration
- `tools/install-omarchy`: one command for a `toploader` command, an apps-menu entry with
  the Poké Ball icon (opens or focuses Toploader), and the bar widget. Safe to re-run;
  `tools/uninstall-omarchy` undoes it.
- Bar widget plugin (`smerlini.toploader`): Poké Ball and collection value in the bar,
  click to open, middle-click to refresh, tooltip with the totals; settings for showing
  the value and the refresh interval.
- `toploader summary` prints the collection totals as JSON from saved prices, and
  `toploader --version` prints the version.

## 1.0.0 — 2026-10-04

First complete version.

### Collection
- Pokémon singles and sealed products in one collection, Japanese and international,
  each line with a language badge.
- Inventory per finish (normal, holo, reverse, 1st edition), condition (Cardmarket scale
  M → PO; Sealed / Sealed with damaged packaging / Opened for sealed), language,
  quantity, price paid and notes.
- Print run for sealed products (First print / Reprint) and an optional personal
  valuation that overrides the market price (marked ✎).
- Sidebar grouping by set, language, type, rarity, category or condition; sorting by
  set, name, value or quantity; filtering.

### Search
- Search by name, card number (`270/SM-P`, `71/SM-P`), TCGdex id (`swsh3 136`) or set
  code (`s4a`, `s4a sealed`, `sm10a box`), across all catalogues at once.
- Space previews a result, Enter adds it.

### Prices
- Japanese cards and all sealed products from TCGCSV (TCGplayer), international cards
  from TCGdex (Cardmarket and TCGplayer), with automatic fallback between sources.
- Shown in € by default, £ or $ on request, using daily ECB exchange rates.
- Automatic refresh of prices older than a day.

### Interface
- Pixel-art Poké Ball logo and wordmark; About screen (`?`).
- Card preview with Sixel images at the correct aspect ratio.
- Table that adapts to the terminal width; colours from the active Omarchy theme.

### Data
- Everything stored in the project folder; automatic migration of older collection
  files.
- Automatic commit and push of the collection to GitHub when the app closes.
- Offline test suite (86 tests) and lint configuration.
