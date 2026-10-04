"""Entry point: `toploader` or `python -m toploader`.

    toploader            open the app (and back up to git when it closes)
    toploader summary    print the collection totals as JSON, for the Omarchy bar widget
    toploader --version
"""

from __future__ import annotations

import argparse
import asyncio
import json


def run_app() -> None:
    # textual-image must probe the terminal before Textual takes over stdin.
    import textual_image.widget  # noqa: F401

    from .app import Toploader
    from .backup import backup
    from .currency import money
    from .paths import ROOT

    app = Toploader()
    app.run()

    app.db.conn.close()  # make sure the collection file is complete before committing
    if app.config.auto_backup:
        copies, unique, value = app.summary()
        message = (f"Collection: {copies} cards ({unique} unique), "
                   f"{money(value, app.currency)}")
        print("Backing up the collection…", flush=True)
        print(backup(ROOT, message))


def compact_money(value: float, currency: str) -> str:
    """Short form for the bar: €842, €2.7k, €12k."""
    from .currency import SYMBOLS

    symbol = SYMBOLS.get(currency, currency + " ")
    if value >= 10_000:
        return f"{symbol}{value / 1000:.0f}k"
    if value >= 1_000:
        return f"{symbol}{value / 1000:.1f}k"
    return f"{symbol}{value:.0f}"


def summary() -> dict:
    """Collection totals from saved prices only: no network, no interface."""
    from .config import Config
    from .currency import CURRENCIES, Rates, money
    from .db import Database
    from .games import GAMES, SOURCE_NAMES
    from .valuation import summarize

    config = Config.load()
    currency = config.currency if config.currency in CURRENCIES else "EUR"
    source = config.price_source if config.price_source in SOURCE_NAMES else "cardmarket"
    games = {g.id: g for g in GAMES}
    game = (games.get(config.game) or GAMES[0])()
    db = Database()
    try:
        s = summarize(db.entries(game.id), game, source, currency, Rates())
    finally:
        db.conn.close()
        asyncio.run(game.close())
    return {
        "copies": s.copies,
        "unique": s.unique,
        "value": round(s.value, 2),
        "currency": currency,
        "text": money(s.value, currency),
        "short": compact_money(s.value, currency),
    }


def main(argv: list[str] | None = None) -> None:
    from . import __version__

    parser = argparse.ArgumentParser(prog="toploader",
                                     description="Your trading card binder, in the terminal.")
    parser.add_argument("--version", action="version", version=f"toploader {__version__}")
    parser.add_argument("command", nargs="?", choices=["summary"],
                        help="summary: print collection totals as JSON")
    args = parser.parse_args(argv)
    if args.command == "summary":
        print(json.dumps(summary()))
    else:
        run_app()


if __name__ == "__main__":
    main()
