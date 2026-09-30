#!/usr/bin/env python3
"""Generate app/favicon.ico (16/32/48, PNG entries) and app/apple-icon.png (180x180).

Run from the repo root:  ../backend/.venv/bin/python frontend/scripts/make-favicon.py
Geometry and colours are regex-parsed from lib/brand.ts (single source of truth). Deterministic.
"""
import io
import re
import struct
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SRC = (ROOT / "lib" / "brand.ts").read_text(encoding="utf-8")
RECT = re.compile(r"\{\s*x:\s*([\d.]+),\s*y:\s*([\d.]+),\s*width:\s*([\d.]+),\s*height:\s*([\d.]+)\s*\}")
SS = 16  # supersampling factor


def rects(name):
    m = re.search(rf"export const {name}\b[^=]*=\s*(.*?);\n", SRC, re.S)
    if not m:
        raise SystemExit(f"brand.ts: {name} not found")
    return [tuple(float(v) for v in r) for r in RECT.findall(m.group(1))]


def const_num(name):
    return float(re.search(rf"export const {name}\s*=\s*([\d.]+);", SRC).group(1))


SIZE = const_num("BRAND_SIZE")
SQUARE = rects("BRAND_SQUARE")[0]
BARS = rects("BRAND_BARS")
BASELINE = rects("BRAND_BASELINE")[0]
INK, PAPER = re.search(r'light:\s*\{\s*ink:\s*"(#\w+)",\s*paper:\s*"(#\w+)"', SRC).groups()


def glyph(px, ink=INK, paper=PAPER, bg=None, inset=0.0):
    """Render the glyph into a px x px RGBA image; `inset` is the padding fraction per side."""
    big = px * SS
    img = Image.new("RGBA", (big, big), bg if bg else (0, 0, 0, 0))
    scale = big * (1 - 2 * inset) / SIZE
    off = big * inset
    d = ImageDraw.Draw(img)

    def box(r, fill):
        x, y, w, h = r
        d.rectangle([off + x * scale, off + y * scale, off + (x + w) * scale - 1, off + (y + h) * scale - 1], fill=fill)

    box(SQUARE, ink)
    for b in BARS:
        box(b, paper)
    box(BASELINE, paper)
    return img.resize((px, px), Image.BOX)


def png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    return buf.getvalue()


def build_ico(sizes):
    pngs = [png_bytes(glyph(s)) for s in sizes]
    head = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries = b""
    for s, data in zip(sizes, pngs):
        entries += struct.pack("<BBBBHHII", s, s, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return head + entries + b"".join(pngs)


app = ROOT / "app"
(app / "favicon.ico").write_bytes(build_ico([16, 32, 48]))
# Apple touch icon: opaque paper background, ink square inset (safe padding; iOS rounds the corners).
(app / "apple-icon.png").write_bytes(png_bytes(glyph(180, bg=PAPER, inset=0.16).convert("RGB")))
print("wrote app/favicon.ico and app/apple-icon.png")
