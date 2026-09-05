"""Draw Ripple's mark as a Windows .ico, with nothing installed to do it.

Run this only when the mark itself changes:

    python tools/make_icon.py

The result is committed, so a build never depends on this script or on an image
library being present. The shape is the same one the browser tab shows: three
concentric rings fading inwards to a solid centre.
"""
from __future__ import annotations

import struct
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets" / "ripple.ico"
SIZES = (16, 24, 32, 48, 64, 128, 256)
SUPERSAMPLE = 4

BLUE = (0x00, 0x6F, 0xCF)          # Ripple blue
NAVY = (0x00, 0x17, 0x5A)          # the solid centre

# (outer radius, stroke width, colour, opacity) as fractions of the icon size.
RINGS = (
    (0.440, 0.080, BLUE, 0.40),
    (0.280, 0.080, BLUE, 0.75),
    (0.130, 0.000, NAVY, 1.00),    # a stroke of zero means a filled disc
)


def coverage(size: int, cx: float, cy: float, outer: float, width: float) -> list[list[float]]:
    """How much of each pixel the ring covers, by sampling inside it."""
    grid = [[0.0] * size for _ in range(size)]
    inner = outer - width if width else 0.0
    step = 1.0 / SUPERSAMPLE
    offset = step / 2
    for py in range(size):
        row = grid[py]
        for px in range(size):
            hits = 0
            for sy in range(SUPERSAMPLE):
                y = py + offset + sy * step - cy
                for sx in range(SUPERSAMPLE):
                    x = px + offset + sx * step - cx
                    d = (x * x + y * y) ** 0.5
                    if d <= outer and (not width or d >= inner):
                        hits += 1
            row[px] = hits / (SUPERSAMPLE * SUPERSAMPLE)
    return grid


def render(size: int) -> bytes:
    """One image, bottom-up 32-bit BGRA, as an icon stores it."""
    pixels = [[(0, 0, 0, 0.0) for _ in range(size)] for _ in range(size)]
    centre = size / 2.0
    for outer_f, width_f, colour, opacity in RINGS:
        cov = coverage(size, centre, centre, outer_f * size, width_f * size)
        for y in range(size):
            for x in range(size):
                a = cov[y][x] * opacity
                if a <= 0:
                    continue
                br, bg, bb, ba = pixels[y][x]
                out_a = a + ba * (1 - a)
                if out_a <= 0:
                    continue
                mix = lambda top, bottom: (top * a + bottom * ba * (1 - a)) / out_a  # noqa: E731
                pixels[y][x] = (mix(colour[0], br), mix(colour[1], bg), mix(colour[2], bb), out_a)
    rows = []
    for y in range(size - 1, -1, -1):                   # bottom-up
        row = bytearray()
        for x in range(size):
            r, g, b, a = pixels[y][x]
            row += bytes((int(b + 0.5), int(g + 0.5), int(r + 0.5), int(a * 255 + 0.5)))
        rows.append(bytes(row))
    return b"".join(rows)


def image(size: int) -> bytes:
    """A DIB: header, then the pixels, then the (unused) transparency mask."""
    header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, size * size * 4,
                         0, 0, 0, 0)
    mask_row = ((size + 31) // 32) * 4                  # padded to 4 bytes
    return header + render(size) + bytes(mask_row * size)


def main() -> None:
    images = [image(s) for s in SIZES]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out = bytearray(struct.pack("<HHH", 0, 1, len(images)))
    offset = 6 + 16 * len(images)
    for size, data in zip(SIZES, images):
        out += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    for data in images:
        out += data
    OUT.write_bytes(bytes(out))
    print(f"wrote {OUT} ({len(out):,} bytes, sizes {', '.join(str(s) for s in SIZES)})")


if __name__ == "__main__":
    main()
