"""The pixel-art logo."""

from toploader import logo


def test_sprites_are_rectangular_and_use_known_colours():
    for art in (logo.BALL, logo.SMALL_BALL):
        rows = logo.sprite(art)
        assert len(rows) == len(rows[0])  # square
        assert set("".join(rows)) <= set(logo.PALETTE) | {"."}


def test_ball_is_symmetric_except_for_shading():
    # Flip each row and ignore the highlight/shadow pixels: the shape must match.
    plain = {"r": "R", "d": "R", "s": "W"}
    for row in logo.sprite(logo.BALL):
        flat = "".join(plain.get(c, c) for c in row)
        assert flat == flat[::-1], row


def test_half_block_rendering_halves_the_height():
    text = logo.to_text(logo.sprite(logo.SMALL_BALL))
    lines = text.plain.split("\n")
    assert len(lines) == 4 and all(len(line) == 8 for line in lines)


def test_wordmark_spells_the_name():
    rows = logo.wordmark("TOP")
    assert len(rows) == 7 and len(rows[0]) == 3 * 5 + 2


def test_png_export(tmp_path):
    logo.to_png(logo.sprite(logo.BALL), tmp_path / "logo.png", scale=4)
    from PIL import Image

    image = Image.open(tmp_path / "logo.png")
    assert image.size == (64, 64)
    assert image.getpixel((0, 0))[3] == 0  # transparent corner
