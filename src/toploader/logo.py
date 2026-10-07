"""The Toploader logo: a pixel-art Poké Ball and a pixel wordmark.

The sprites are plain text grids, one character per pixel ("." is
transparent), so they can be drawn in the terminal with half-block
characters (two pixels per cell, which keeps the pixels roughly square) or
exported as PNGs for the README.
"""

from __future__ import annotations

import os

from rich.style import Style
from rich.text import Text

PALETTE = {
    "K": "#141418",  # outline and centre band
    "k": "#3b3d4a",  # centre band of the small ball, visible on dark backgrounds
    "R": "#e3350d",  # red top
    "r": "#ff8a65",  # highlight on the red
    "d": "#a3260a",  # red shadow
    "W": "#f5f5f5",  # white bottom
    "s": "#b9bdc9",  # shadow on the white
    "B": "#ffffff",  # button
    "g": "#c9ccd6",  # button ring
}

BALL = """
.....KKKKKK.....
...KKRRRRRRKK...
..KRRRRRRRRRRK..
.KRrrRRRRRRRRdK.
.KRrRRRRRRRRRdK.
KRRRRRKKKKRRRRdK
KRRRRKggggKRRRdK
KKKKKKgBBgKKKKKK
KKKKKKgBBgKKKKKK
KWWWWKggggKWWWsK
KWWWWWKKKKWWWWsK
.KWWWWWWWWWWWsK.
.KWWWWWWWWWWssK.
..KWWWWWWWWssK..
...KKssssssKK...
.....KKKKKK.....
"""

SMALL_BALL = """
..RRRR..
.RrRRRd.
RrRRRRRd
kkkBBkkk
kkkBBkkk
WWWWWWWs
.WWWWWs.
..ssss..
"""

# SMALL_BALL for terminals without gapless half blocks: one pixel per cell.
SMALL_BALL_CELLS = """
.rRRRRd.
RRRRRRRd
kkkBBkkk
.WWWWWs.
"""

# 5x7 pixel font, just the letters of the name.
GLYPHS = {
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
}


def sprite(art: str) -> list[str]:
    rows = [row for row in art.strip().splitlines()]
    assert len({len(r) for r in rows}) == 1, "sprite rows must have equal length"
    return rows


def wordmark(word: str = "TOPLOADER") -> list[str]:
    """The word in the pixel font: red on top, white below, like the ball."""
    rows = []
    for y in range(7):
        line = ".".join(GLYPHS[ch][y] for ch in word)
        rows.append(line.replace("#", "R" if y < 4 else "W"))
    return rows


def half_blocks_ok() -> bool:
    """Apple's Terminal leaves a gap between rows of block characters, which
    stripes half-block art; there, sprites are drawn with coloured cells."""
    return os.environ.get("TERM_PROGRAM") != "Apple_Terminal"


def small_ball() -> Text:
    """The top bar's logo, four cells tall either way."""
    if half_blocks_ok():
        return to_text(sprite(SMALL_BALL))
    return to_cells(sprite(SMALL_BALL_CELLS))


def to_cells(rows: list[str]) -> Text:
    """Render a sprite as coloured cells, one pixel per cell (no gaps anywhere)."""
    text = Text(no_wrap=True)
    for y, row in enumerate(rows):
        for ch in row:
            color = PALETTE.get(ch)
            text.append(" ", Style(bgcolor=color) if color else None)
        if y + 1 < len(rows):
            text.append("\n")
    return text


def to_text(rows: list[str]) -> Text:
    """Render a sprite with half blocks: each cell shows two stacked pixels.

    Where half blocks don't join up, each pair of rows becomes one row of
    coloured cells instead (the upper pixel wins), at the same size."""
    if len(rows) % 2:
        rows = rows + ["." * len(rows[0])]
    if not half_blocks_ok():
        return to_cells([
            "".join(t if t in PALETTE else b for t, b in zip(top, bottom, strict=True))
            for top, bottom in zip(rows[::2], rows[1::2], strict=True)
        ])
    text = Text(no_wrap=True)
    for y in range(0, len(rows), 2):
        for top, bottom in zip(rows[y], rows[y + 1], strict=True):
            top_c, bottom_c = PALETTE.get(top), PALETTE.get(bottom)
            if top_c and bottom_c:
                text.append("▀", Style(color=top_c, bgcolor=bottom_c))
            elif top_c:
                text.append("▀", Style(color=top_c))
            elif bottom_c:
                text.append("▄", Style(color=bottom_c))
            else:
                text.append(" ")
        if y + 2 < len(rows):
            text.append("\n")
    return text


def banner() -> Text:
    """Big ball next to the wordmark, for the About and empty screens."""
    ball = sprite(BALL)
    if not half_blocks_ok():
        # The pixel font needs both pixels of each cell, so spell the name instead.
        ball_text = to_text(ball)
        lines = ball_text.split("\n")
        word = Text("T O P L O A D E R", style=f"bold {PALETTE['R']}")
        out = Text(no_wrap=True)
        for i, line in enumerate(lines):
            out.append_text(line)
            if i == len(lines) // 2 - 1:
                out.append("    ")
                out.append_text(word)
            if i + 1 < len(lines):
                out.append("\n")
        return out
    word = wordmark()
    # Centre the 7-pixel wordmark (padded to 8) against the 16-pixel ball.
    pad = "." * len(word[0])
    word = [pad] * 4 + word + [pad] + [pad] * 4
    gap = "...."
    return to_text([b + gap + w for b, w in zip(ball, word, strict=True)])


def to_png(rows: list[str], path, scale: int = 16, background: str | None = None) -> None:
    from PIL import Image

    height, width = len(rows), len(rows[0])
    bg = (0, 0, 0, 0) if background is None else _rgba(background)
    image = Image.new("RGBA", (width, height), bg)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in PALETTE:
                image.putpixel((x, y), _rgba(PALETTE[ch]))
    image.resize((width * scale, height * scale), Image.NEAREST).save(path)


def _rgba(color: str) -> tuple[int, int, int, int]:
    color = color.lstrip("#")
    return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16), 255)
