"""Draws the app icon source (`desktop/icon.png`, 1024x1024) with the standard library only.

The mark is a character, not a symbol: a round little moon rising from the lower right of the tile,
half of it in soft shadow. The soft edge between its lit and shaded halves is the penumbra the
product is named after, so it is drawn as a gradient band rather than a hard line. It has sleepy
eyes and a small smile on the lit side, and a tiny moon of its own keeps it company. The rules
followed are those of a mascot mark: a handful of large rounded shapes, one dominant silhouette
emerging from a corner and filling most of the tile, three colours (cream and copper on a muted
night plum), and nothing thin enough to vanish at 32px.

Every shape is a signed distance, so each pixel's coverage is computed analytically and the edges
are antialiased without supersampling. No text, no fonts, no dependencies. Regenerate the platform
icons with `cargo tauri icon ../icon.png` from `desktop/src-tauri`, then delete the `android` and
`ios` folders and the Windows Store logos (`Square*Logo.png`, `StoreLogo.png`) it adds: the bundle
lists only the five icons in `tauri.conf.json`.
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

SIZE = 1024
# The macOS icon grid: an 824px rounded tile inside the 1024px canvas.
TILE = (100, 100, 924, 924)
TILE_RADIUS = 185

NIGHT = (58, 44, 74)        # the tile: a muted night plum
NIGHT_HIGH = (76, 60, 96)   # its lighter top
CREAM = (246, 232, 206)     # the lit half
CREAM_HIGH = (255, 246, 228)
COPPER = (184, 104, 58)     # the shaded half
COPPER_LOW = (132, 72, 44)
INK = (58, 40, 60)          # eyes and smile

MOON = (612, 664, 350)      # centre x, centre y, radius: rising from the lower right
LIGHT = (768, 540, 410)     # the lit disc; the moon outside it is in shadow
PENUMBRA = 46.0             # width of the soft terminator band, in px
SATELLITE = (292, 300, 50)


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else min(v, hi)


def smooth(v: float) -> float:
    v = clamp(v)
    return v * v * (3 - 2 * v)


def mix(a, b, t: float):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def circle(x: float, y: float, c) -> float:
    """Signed distance to a circle (negative inside)."""
    return math.hypot(x - c[0], y - c[1]) - c[2]


def cover(d: float) -> float:
    """Pixel coverage from a signed distance: a one-pixel antialiased edge."""
    return clamp(0.5 - d)


def rounded_rect(x: float, y: float, box, r: float) -> float:
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hx, hy = (x1 - x0) / 2 - r, (y1 - y0) / 2 - r
    qx, qy = abs(x - cx) - hx, abs(y - cy) - hy
    return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - r


def arc(x: float, y: float, cx: float, cy: float, r: float, width: float, lower: bool) -> float:
    """Signed distance to a half-circle stroke with round caps: the lower half for a sleepy eye or
    a smile."""
    dx, dy = x - cx, y - cy
    if (dy >= 0) == lower:
        return abs(math.hypot(dx, dy) - r) - width / 2
    # Past the ends of the half circle: distance to the nearer round cap.
    return min(math.hypot(x - (cx - r), y - cy), math.hypot(x - (cx + r), y - cy)) - width / 2


def over(base, colour, alpha: float):
    return mix(base, colour, clamp(alpha))


def pixel(x: float, y: float):
    """(r, g, b, a) for one pixel centre."""
    tile = cover(rounded_rect(x, y, TILE, TILE_RADIUS))
    if tile <= 0:
        return (0, 0, 0, 0)
    # The tile: night plum, lighter toward the top.
    colour = mix(NIGHT_HIGH, NIGHT, smooth((y - TILE[1]) / (TILE[3] - TILE[1])))

    # Two small stars.
    for sx, sy, sr in ((196, 470, 9), (452, 208, 7)):
        colour = over(colour, CREAM, 0.75 * cover(circle(x, y, (sx, sy, sr))))

    # The little moon: cream with its own sliver of shade on the left.
    sat = cover(circle(x, y, SATELLITE))
    if sat > 0:
        shade = smooth((SATELLITE[0] - 10 - x) / 40 + 0.5)
        colour = over(colour, mix(CREAM, COPPER, shade), sat)

    # The moon. Its lit half is the part inside LIGHT; the band either side of that edge is the
    # penumbra, a smooth blend rather than a line.
    moon = cover(circle(x, y, MOON))
    if moon > 0:
        lit = smooth(0.5 - circle(x, y, LIGHT) / PENUMBRA)
        # Soft modelling: brighter toward the top right of the lit side, deeper toward the lower left
        # of the shaded side.
        glow = clamp(1 - math.hypot(x - 760, y - 450) / 420)
        lit_colour = mix(CREAM, CREAM_HIGH, glow * 0.8)
        deep = clamp(math.hypot(x - 360, y - 860) / 520)
        shade_colour = mix(COPPER_LOW, COPPER, deep)
        body = mix(shade_colour, lit_colour, lit)
        colour = over(colour, body, moon)

        # The face, on the lit side: two sleepy eyes, a small smile and a blush of copper.
        for bx, by in ((604, 704), (836, 704)):
            blush = 1 - math.hypot((x - bx) / 40, (y - by) / 22)
            colour = over(colour, COPPER, 0.32 * smooth(blush * 2))
        for ex in (648, 792):
            colour = over(colour, INK, cover(arc(x, y, ex, 644, 29, 17, lower=True)))
        colour = over(colour, INK, cover(arc(x, y, 720, 714, 23, 14, lower=True)))

    return (round(colour[0]), round(colour[1]), round(colour[2]), round(255 * tile))


def png(path: Path) -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    rows = bytearray()
    for y in range(SIZE):
        rows.append(0)
        for x in range(SIZE):
            rows.extend(pixel(x + 0.5, y + 0.5))
    header = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + chunk(b"IEND", b"")
    )


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "icon.png"
    png(out)
    print(f"wrote {out}")
