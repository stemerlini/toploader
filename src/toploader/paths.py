"""Where the app keeps its data.

Run from the project folder (./toploader, or an editable install), everything
lives inside it. A standalone build or a regular install uses the platform's
data folder instead: ~/Library/Application Support/Toploader on macOS,
~/.local/share/toploader on Linux. Set TOPLOADER_HOME to choose any folder.
"""

import os
import sys
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2]


def default_root() -> Path:
    if not getattr(sys, "frozen", False) and (SOURCE_ROOT / "pyproject.toml").exists():
        return SOURCE_ROOT
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Toploader"
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or Path.home()) / "Toploader"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "toploader"


ROOT = Path(os.environ.get("TOPLOADER_HOME") or default_root())

DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "cache"
CONFIG_DIR = ROOT / "data"
IMAGE_DIR = CACHE_DIR / "images"

USER_AGENT = "toploader/0.1 (personal card collection tracker)"
