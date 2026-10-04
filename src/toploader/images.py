"""Download and cache card images on disk."""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx

from .paths import IMAGE_DIR, USER_AGENT


def cached_path(url: str) -> Path:
    digest = hashlib.sha1(url.encode()).hexdigest()[:16]
    return IMAGE_DIR / f"{digest}{Path(url).suffix or '.png'}"


async def fetch_image(url: str) -> Path | None:
    if not url:
        return None
    path = cached_path(url)
    if path.exists():
        return path
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(
        timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    ) as client:
        response = await client.get(url)
        if response.status_code != 200:
            return None
    tmp = path.with_suffix(".part")
    tmp.write_bytes(response.content)
    tmp.rename(path)
    return path
