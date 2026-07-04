#!/usr/bin/env python3
"""Generate res/drawable/icon.png (192x192) with the Python stdlib only:
blue rounded square with a white route line between two endpoint dots."""

import struct
import zlib

W = H = 192
BLUE = (26, 115, 232, 255)
WHITE = (255, 255, 255, 255)
CLEAR = (0, 0, 0, 0)


def dist_to_segment(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    c1 = vx * wx + vy * wy
    c2 = vx * vx + vy * vy
    t = 0 if c2 == 0 else max(0.0, min(1.0, c1 / c2))
    dx, dy = px - (ax + t * vx), py - (ay + t * vy)
    return (dx * dx + dy * dy) ** 0.5


# Route polyline waypoints (a wiggly A→B path) and endpoint dots.
SEGS = [(48, 150, 78, 110), (78, 110, 70, 74), (70, 74, 120, 84), (120, 84, 144, 44)]
DOTS = [(48, 150, 14), (144, 44, 14)]
ROUND = 34  # corner radius of the background


def pixel(x, y):
    # Rounded-rect background test.
    rx = min(x, W - 1 - x)
    ry = min(y, H - 1 - y)
    if rx < ROUND and ry < ROUND:
        if ((rx - ROUND) ** 2 + (ry - ROUND) ** 2) ** 0.5 > ROUND:
            return CLEAR
    # Route line + dots in white.
    for ax, ay, bx, by in SEGS:
        if dist_to_segment(x, y, ax, ay, bx, by) < 8:
            return WHITE
    for cx, cy, r in DOTS:
        d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
        if d < r:
            return BLUE if d < r - 7 else WHITE
    return BLUE


rows = b""
for y in range(H):
    row = b"\x00"
    for x in range(W):
        row += bytes(pixel(x, y))
    rows += row


def chunk(tag, data):
    c = struct.pack(">I", len(data)) + tag + data
    return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


png = (
    b"\x89PNG\r\n\x1a\n"
    + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0))
    + chunk(b"IDAT", zlib.compress(rows, 9))
    + chunk(b"IEND", b"")
)

with open("res/drawable/icon.png", "wb") as f:
    f.write(png)
print("icon.png written:", len(png), "bytes")
