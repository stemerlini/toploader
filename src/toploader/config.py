"""Small JSON config persisted between runs."""

import json
from dataclasses import asdict, dataclass

from .paths import CONFIG_DIR

CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class Config:
    game: str = "pokemon"
    currency: str = "EUR"  # EUR | GBP | USD, prices are converted to it
    price_source: str = "cardmarket"  # "cardmarket" (EUR) or "tcgplayer" (USD)
    group_by: str = "set"  # set | type | rarity | category | condition
    sort_by: str = "set"  # set | name | value | quantity

    @classmethod
    def load(cls) -> "Config":
        try:
            data = json.loads(CONFIG_FILE.read_text())
        except (OSError, ValueError):
            return cls()
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(asdict(self), indent=2))
