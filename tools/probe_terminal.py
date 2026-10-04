"""Print what the terminal reports about cell size and graphics support.

Run it in the same terminal you use for Toploader:  .venv/bin/python tools/probe_terminal.py
"""

import fcntl
import os
import struct
import sys
import termios

rows, cols, xpix, ypix = struct.unpack(
    "HHHH", fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, b"\0" * 8)
)
print(f"TERM={os.environ.get('TERM')}  TERM_PROGRAM={os.environ.get('TERM_PROGRAM')}")
print(f"ioctl: {cols} cols x {rows} rows, {xpix} x {ypix} px")
if xpix and ypix:
    print(f"       → cell {xpix / cols:.2f} x {ypix / rows:.2f} px")

from textual_image._terminal import probe_terminal  # noqa: E402
from textual_image.renderable import Image  # noqa: E402

caps = probe_terminal()
print(f"textual-image: cell {caps.cell_size.width} x {caps.cell_size.height} px, "
      f"sixel={caps.sixel}, kitty graphics={caps.tgp}")
print(f"renderer chosen: {Image.__module__.rsplit('.', 1)[-1]}")
