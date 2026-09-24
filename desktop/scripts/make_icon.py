"""Draws the app icon source (`desktop/icon.png`, 1024x1024) with the standard library only.

The mark is the product's signature, a citation's highlighter stroke (DESIGN.md §2): three lines
of text on a copper tile, one of them underlined by a stroke with a small superscript reference
number. No text is rendered, so there is no font dependency. Regenerate the platform icons with
`cargo tauri icon desktop/icon.png` from `desktop/src-tauri`.
"""

import struct
import zlib
from pathlib import Path

SIZE = 1024
# The palette's own values: Study's copper tile, Paper's ink and cream.
COPPER = (184, 98, 38)
CREAM = (250, 244, 232)
INK = (60, 36, 20)
STROKE = (247, 205, 120)


def rounded(x, y, x0, y0, x1, y1, r):
    if x < x0 or x > x1 or y < y0 or y > y1:
        return False
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def pixel(x, y):
    # macOS-style inset tile: 100px margin, 180px corner radius.
    if not rounded(x, y, 100, 100, 923, 923, 185):
        return (0, 0, 0, 0)
    # Three lines of "text" as cream bars.
    for top, right in ((330, 760), (470, 700), (610, 640)):
        if rounded(x, y, 240, top, right, top + 56, 28):
            return (*CREAM, 255)
    # The highlighter stroke under the middle line, and its reference number.
    if rounded(x, y, 232, 540, 708, 566, 13):
        return (*STROKE, 255)
    if (x - 760) ** 2 + (y - 462) ** 2 <= 30 ** 2:
        return (*STROKE, 255)
    return (*COPPER, 255)


def png(path: Path) -> None:
    rows = b"".join(
        b"\x00" + b"".join(bytes(pixel(x, y)) for x in range(SIZE)) for y in range(SIZE)
    )

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)
    body = chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b"")
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + body)


if __name__ == "__main__":
    png(Path(__file__).resolve().parents[1] / "icon.png")
