"""Draw the macOS app icon: the pixel Poké Ball on a dark rounded square.

    python packaging/make_icon.py OUT.icns [PREVIEW.png]

Follows Apple's icon grid (an 824 px rounded square inside a 1024 px canvas),
so it sits next to other apps in the Dock and Launchpad without being boxed in.
"""

import sys

from PIL import Image, ImageDraw

from toploader.logo import BALL, PALETTE, _rgba, sprite

CANVAS, TILE, RADIUS = 1024, 824, 185
TILE_COLOR = "#3a3e50"
PIXEL = 36  # 16 sprite pixels -> 576 px ball


def icon() -> Image.Image:
    image = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    edge = (CANVAS - TILE) // 2
    ImageDraw.Draw(image).rounded_rectangle(
        (edge, edge, edge + TILE - 1, edge + TILE - 1), RADIUS, fill=_rgba(TILE_COLOR))
    rows = sprite(BALL)
    ball = Image.new("RGBA", (len(rows[0]), len(rows)), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in PALETTE:
                ball.putpixel((x, y), _rgba(PALETTE[ch]))
    ball = ball.resize((ball.width * PIXEL, ball.height * PIXEL), Image.NEAREST)
    offset = (CANVAS - ball.width) // 2
    image.alpha_composite(ball, (offset, offset))
    return image


if __name__ == "__main__":
    image = icon()
    image.save(sys.argv[1], sizes=[(s, s) for s in (16, 32, 64, 128, 256, 512, 1024)])
    if len(sys.argv) > 2:
        image.save(sys.argv[2])
