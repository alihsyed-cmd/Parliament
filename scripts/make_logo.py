#!/usr/bin/env python3
"""Regenerate the Parliament app logo and every icon asset from one source of truth.

The mark is a legislature — spire, dome, entablature, three columns, base — in the
app's paper cream on its brick-red accent (both lifted from app/globals.css).

    python3 scripts/make_logo.py

Rasterizing uses headless Google Chrome, so no image libraries are required.
Writes into frontend/app/ (icon.svg, favicon.ico, apple-icon.png) and
frontend/public/ (icon-192.png, icon-512.png, icon-maskable-512.png).
"""
import os, struct, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "frontend", "app")
PUBLIC = os.path.join(ROOT, "frontend", "public")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Palette — the OKLCH tokens in app/globals.css, resolved to sRGB.
RED_HI, RED, RED_LO = "#d4462f", "#c83b2c", "#a52b1e"   # --accent, lightened / deepened
CREAM = "#fbf7ee"                                        # --paper

# Mark geometry, authored on a 512 canvas: bbox x 96..416, y 98..414 (centred).
COLUMNS = (186, 256, 326)


def mark(scale=1.0, fill=CREAM):
    def at(v, origin=256):
        return origin + (v - origin) * scale

    def bar(x, y, w, h, r):
        return (f'<rect x="{at(x):.2f}" y="{at(y):.2f}" width="{w*scale:.2f}" '
                f'height="{h*scale:.2f}" rx="{r*scale:.2f}" ry="{r*scale:.2f}" fill="{fill}"/>')

    def dome(cx, cy, r):
        cx, cy, r = at(cx), at(cy), r * scale
        return (f'<path d="M {cx-r:.2f} {cy:.2f} A {r:.2f} {r:.2f} 0 0 1 '
                f'{cx+r:.2f} {cy:.2f} Z" fill="{fill}"/>')

    return "\n  ".join([
        bar(249, 98, 14, 34, 7),                                  # spire
        dome(256, 232, 106),                                      # dome
        bar(118, 244, 276, 32, 11),                               # entablature
        *[bar(cx - 16, 288, 32, 80, 7) for cx in COLUMNS],        # columns
        bar(96, 378, 320, 36, 13),                                # base
    ])


ROUNDED = '<rect width="512" height="512" rx="112" ry="112" fill="url(#pg)"/>'
FULL = '<rect width="512" height="512" fill="url(#pg)"/>'


def svg(ground=ROUNDED, scale=1.0):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512" role="img" aria-label="Parliament">
  <title>Parliament</title>
  <defs>
    <linearGradient id="pg" x1="0" y1="0" x2="0.35" y2="1">
      <stop offset="0" stop-color="{RED_HI}"/>
      <stop offset="0.55" stop-color="{RED}"/>
      <stop offset="1" stop-color="{RED_LO}"/>
    </linearGradient>
  </defs>
  {ground}
  {mark(scale)}
</svg>
'''


def rasterize(svg_path, size, out_png):
    """Screenshot the SVG at an exact pixel size, preserving transparency."""
    html = (f'<style>html,body{{margin:0;background:transparent}}'
            f'img{{display:block;width:{size}px;height:{size}px}}</style>'
            f'<img src="file://{svg_path}">')
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as fh:
        fh.write(html)
        page = fh.name
    try:
        subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             "--default-background-color=00000000", "--force-device-scale-factor=1",
             f"--window-size={size},{size}", f"--screenshot={out_png}", f"file://{page}"],
            check=True, capture_output=True)
    finally:
        os.unlink(page)


def write_ico(pngs, out_path):
    """Multi-size .ico with PNG payloads — read by every current browser."""
    blobs = [(open(p, "rb").read(), s) for p, s in pngs]
    header = struct.pack("<HHH", 0, 1, len(blobs))
    offset = len(header) + 16 * len(blobs)
    entries, payload = b"", b""
    for data, size in blobs:
        entries += struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(data), offset)
        payload += data
        offset += len(data)
    open(out_path, "wb").write(header + entries + payload)


def main():
    if not os.path.exists(CHROME):
        sys.exit(f"Google Chrome not found at {CHROME} — needed to rasterize the PNGs.")
    tile_svg = os.path.join(APP, "icon.svg")
    open(tile_svg, "w").write(svg(ROUNDED))

    with tempfile.TemporaryDirectory() as tmp:
        # Full-bleed for iOS (which applies its own squircle mask) and for the
        # Android adaptive icon, whose mark is inset into the 80% safe zone.
        bleed = os.path.join(tmp, "fullbleed.svg")
        maskable = os.path.join(tmp, "maskable.svg")
        open(bleed, "w").write(svg(FULL))
        open(maskable, "w").write(svg(FULL, scale=0.68))

        ico_parts = []
        for size in (16, 32, 48):
            png = os.path.join(tmp, f"tile-{size}.png")
            rasterize(tile_svg, size, png)
            ico_parts.append((png, size))
        write_ico(ico_parts, os.path.join(APP, "favicon.ico"))

        rasterize(bleed, 180, os.path.join(APP, "apple-icon.png"))
        rasterize(tile_svg, 192, os.path.join(PUBLIC, "icon-192.png"))
        rasterize(tile_svg, 512, os.path.join(PUBLIC, "icon-512.png"))
        rasterize(maskable, 512, os.path.join(PUBLIC, "icon-maskable-512.png"))

    for path in ("frontend/app/icon.svg", "frontend/app/favicon.ico", "frontend/app/apple-icon.png",
                 "frontend/public/icon-192.png", "frontend/public/icon-512.png",
                 "frontend/public/icon-maskable-512.png"):
        print(f"  {path}  ({os.path.getsize(os.path.join(ROOT, path))} bytes)")


if __name__ == "__main__":
    main()
