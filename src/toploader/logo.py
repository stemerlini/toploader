"""The Toploader logo: a pixel-art Poké Ball and a pixel wordmark.

The sprites are plain text grids, one character per pixel ("." is
transparent), so they can be drawn in the terminal with half-block
characters (two pixels per cell, which keeps the pixels roughly square) or
exported as PNGs for the README.
"""

from __future__ import annotations

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


def to_text(rows: list[str]) -> Text:
    """Render a sprite with half blocks: each cell shows two stacked pixels."""
    if len(rows) % 2:
        rows = rows + ["." * len(rows[0])]
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
