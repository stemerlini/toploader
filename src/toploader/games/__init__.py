"""Registry of supported trading card games."""

from .base import SOURCE_NAMES, Catalog, Game, SearchResult
from .pokemon import Pokemon

GAMES: list[type[Game]] = [Pokemon]

__all__ = ["GAMES", "SOURCE_NAMES", "Catalog", "Game", "SearchResult"]
