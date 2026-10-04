"""Everything the app stores lives inside the project folder.

Set TOPLOADER_HOME to keep the collection somewhere else.
"""

import os
from pathlib import Path

ROOT = Path(os.environ.get("TOPLOADER_HOME") or Path(__file__).resolve().parents[2])

DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "cache"
CONFIG_DIR = ROOT / "data"
IMAGE_DIR = CACHE_DIR / "images"

USER_AGENT = "toploader/0.1 (personal card collection tracker)"
