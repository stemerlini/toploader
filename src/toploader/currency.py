"""Currency display and conversion with the daily ECB rates (frankfurter.dev)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx

from .paths import CACHE_DIR, USER_AGENT

CURRENCIES = ["EUR", "GBP", "USD"]
SYMBOLS = {"EUR": "€", "GBP": "£", "USD": "$"}
# The currency each price source quotes in.
SOURCE_CURRENCY = {"cardmarket": "EUR", "tcgplayer": "USD"}

RATES_FILE = CACHE_DIR / "rates.json"
RATES_URL = "https://api.frankfurter.dev/v1/latest"
MAX_AGE = timedelta(hours=12)


def money(value: float | None, currency: str) -> str:
    return "—" if value is None else f"{SYMBOLS.get(currency, currency + ' ')}{value:,.2f}"


class Rates:
    """Exchange rates relative to the euro, cached on disk."""

    def __init__(self) -> None:
        self.rates: dict[str, float] = {"EUR": 1.0}
        self.date = ""
        self.fetched_at: datetime | None = None
        try:
            data = json.loads(RATES_FILE.read_text())
            self.rates.update(data["rates"])
            self.date = data["date"]
            self.fetched_at = datetime.fromisoformat(data["fetched_at"])
        except (OSError, ValueError, KeyError):
            pass

    @property
    def stale(self) -> bool:
        return not self.fetched_at or datetime.now(UTC) - self.fetched_at > MAX_AGE

    async def update(self) -> None:
        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": USER_AGENT}) as client:
            response = await client.get(
                RATES_URL, params={"base": "EUR", "symbols": ",".join(CURRENCIES[1:])}
            )
            response.raise_for_status()
            data = response.json()
        self.rates = {"EUR": 1.0, **data["rates"]}
        self.date = data["date"]
        self.fetched_at = datetime.now(UTC)
        RATES_FILE.parent.mkdir(parents=True, exist_ok=True)
        RATES_FILE.write_text(json.dumps({
            "rates": data["rates"], "date": self.date,
            "fetched_at": self.fetched_at.isoformat(timespec="seconds"),
        }))

    def convert(self, value: float | None, source: str, target: str) -> float | None:
        """Convert between currencies; None when a rate is missing."""
        if value is None or source == target:
            return value
        if source not in self.rates or target not in self.rates:
            return None
        return value / self.rates[source] * self.rates[target]
