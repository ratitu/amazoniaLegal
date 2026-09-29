#!/usr/bin/env python3
"""Render the daily INPE fire-spot CSVs as a 2 fps timelapse GIF over ESRI satellite imagery.

One CSV per frame. Every spot of that day is drawn on a Web-Mercator ESRI World
Imagery mosaic, the whole region is visible in each frame, and the GIF advances
at 2 frames per second.

The basemap mosaic and the boundary outline are static, so they are fetched and
drawn exactly once and cached on disk; only the spots are re-plotted per frame.

Usage:
    python3 make_gif.py                      # clipped/ -> focos_timelapse.gif
    python3 make_gif.py --input raw          # every spot in Brazil
    python3 make_gif.py --size 1280x960      # smaller frames
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import time
from io import BytesIO
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely
from PIL import Image, ImageDraw

from clip_focos import load_boundary

BASE = Path(__file__).resolve().parent
FRAMES = BASE / "frames"

TILE = 256
MAX_LAT = 85.05112878
ESRI_TILE_URL = (
    "https://server.arcgisonline.com/ArcGIS/rest/services"
    "/World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
UA = "Mozilla/5.0 (X11; Linux x86_64) amazoniaLegal-focos-timelapse"

SPOT_COLOR = "#ff4d1a"
SPOT_HALO = "#3a0a00"
BOUNDARY_COLOR = (255, 255, 255)
BOUNDARY_SHADOW = (0, 0, 0)

DATE_RE = re.compile(r"(\d{4})(\d{2})(\d{2})")


# --------------------------------------------------------------------------- #
# Web Mercator (EPSG:3857)
# --------------------------------------------------------------------------- #

def to_mercator(lon, lat):
    """Longitude/latitude -> normalised world coordinates in [0, 1].

    y is the inverse gudermannian: asinh(tan(lat)). Using atan(sinh(lat))
    (the forward gudermannian) misplaces latitudes by up to ~66 km at 18 deg
    and ~1060 km at 45 deg (verified against pyproj EPSG:3857).
    """
    lat = np.clip(np.asarray(lat, dtype=float), -MAX_LAT, MAX_LAT)
    x = (np.asarray(lon, dtype=float) + 180.0) / 360.0
    y = 0.5 - np.arcsinh(np.tan(np.radians(lat))) / np.pi
    return x, y


def world_pixels(lon, lat, zoom: float):
    """Longitude/latitude -> pixel coordinates in the zoom-level tile pyramid."""
    world = TILE * (2.0**zoom)
    x, y = to_mercator(lon, lat)
    return x * world, y * world


def zoom_for(west, east, south, north, target: int) -> int:
    """Zoom whose short side comes closest to `target` pixels.

    A span is `frac * TILE * 2**z` pixels, and `world_pixels(..., 0)` already
    returns that at z=0, so the needed 2**z is just target / span_at_zoom_0.
    Taking the smaller span makes the frame's short axis the limiting one.
    Rounding to the nearest zoom keeps the mosaic within ~20% of the target in
    either direction; rounding down instead would resample z5 up to 1200px
    (2.3x) and visibly blur it. Pass --zoom for an exact fit.
    """
    x0, y0 = world_pixels(west, north, 0)
    x1, y1 = world_pixels(east, south, 0)
    span = max(min(x1 - x0, y1 - y0), 1e-12)
    return max(0, min(19, int(round(math.log2(max(target / span, 1.0))))))


# --------------------------------------------------------------------------- #
# Basemap mosaic
# --------------------------------------------------------------------------- #

def fetch_tile(session, zoom: int, x: int, y: int) -> Image.Image:
    """One ESRI World Imagery tile, or a neutral dark tile when the service 404s."""
    url = ESRI_TILE_URL.format(z=zoom, y=y, x=x)
    for attempt in range(3):
        try:
            resp = session.get(url, headers={"User-Agent": UA}, timeout=30)
            if resp.status_code == 200 and resp.content:
                return Image.open(BytesIO(resp.content)).convert("RGB")
            break
        except Exception:
            if attempt == 2:
                raise
    return Image.new("RGB", (TILE, TILE), (24, 28, 32))


def build_mosaic(session, zoom: int, left: float, top: float, right: float, bottom: float) -> Image.Image:
    """Stitch the tiles covering a pixel window and crop to it exactly."""
    tx0, tx1 = int(left // TILE), int(right // TILE)
    ty0, ty1 = int(top // TILE), int(bottom // TILE)
    limit = 2**zoom - 1
    tx0, tx1 = max(tx0, 0), min(tx1, limit)
    ty0, ty1 = max(ty0, 0), min(ty1, limit)

    mosaic = Image.new("RGB", ((tx1 - tx0 + 1) * TILE, (ty1 - ty0 + 1) * TILE))
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            mosaic.paste(fetch_tile(session, zoom, tx, ty), ((tx - tx0) * TILE, (ty - ty0) * TILE))

    box = (int(round(left)) - tx0 * TILE, int(round(top)) - ty0 * TILE,
           int(round(right)) - tx0 * TILE, int(round(bottom)) - ty0 * TILE)
    return mosaic.crop(box)


def draw_boundary(image: Image.Image, geom, zoom: int, x0: float, y0: float) -> int:
    """Burn the boundary outline into the static basemap so frames stay cheap."""
    draw = ImageDraw.Draw(image)
    rings = 0
    for polygon in geom.geoms:
        for ring in (polygon.exterior, *polygon.interiors):
            coords = shapely.get_coordinates(ring)
            px, py = world_pixels(coords[:, 0], coords[:, 1], zoom)
            line = np.column_stack([px - x0, py - y0])
            if line.shape[0] < 2:
                continue
            pts = [tuple(v) for v in line]
            draw.line(pts, fill=BOUNDARY_SHADOW, width=3, joint="curve")
            draw.line(pts, fill=BOUNDARY_COLOR, width=1, joint="curve")
            rings += 1
    return rings


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #

def frame_date(path: Path) -> str:
    match = DATE_RE.search(path.name)
    if not match:
        raise SystemExit(f"cannot read a date from {path.name}")
    y, m, d = match.groups()
    return f"{y}-{m}-{d}"


def read_points(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Longitude/latitude of every spot in a daily CSV, unparseable rows dropped."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    lons = pd.to_numeric(df["lon"].str.strip(), errors="coerce").to_numpy()
    lats = pd.to_numeric(df["lat"].str.strip(), errors="coerce").to_numpy()
    ok = np.isfinite(lons) & np.isfinite(lats)
    return lons[ok], lats[ok]


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def parse_size(text: str) -> tuple[int, int]:
    parts = text.lower().replace(",", "x").split("x")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("size must look like 1600x1200")
    width, height = (int(round(float(p) / 2)) * 2 for p in parts)
    if width < 64 or height < 64:
        raise argparse.ArgumentTypeError("size must be at least 64x64")
    return width, height


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", type=Path, default=BASE / "clipped", help="directory of daily CSVs (default: clipped/)")
    ap.add_argument("--out", type=Path, default=BASE / "focos_timelapse.gif")
    ap.add_argument("--size", type=parse_size, default=parse_size("1600x1200"), help="WxH frame size in pixels")
    ap.add_argument("--zoom", type=int, default=None, help="tile zoom (default: highest that fills the frame)")
    ap.add_argument("--fps", type=float, default=2.0)
    ap.add_argument("--force", action="store_true", help="rebuild cached basemap and frames")
    args = ap.parse_args()

    files = sorted(args.input.glob("focos_diario_br_*.csv"))
    if not files:
        raise SystemExit(f"no focos_diario_br_*.csv in {args.input}")
    width, height = args.size

    # 1. Geographic extent: the boundary, widened if the chosen data reaches past it.
    geom = load_boundary()
    west, south, east, north = map(float, geom.bounds)
    points = {}
    for path in files:
        lons, lats = read_points(path)
        points[path] = (lons, lats)
        if lons.size:
            west, south = min(west, float(lons.min())), min(south, float(lats.min()))
            east, north = max(east, float(lons.max())), max(north, float(lats.max()))

    zoom = args.zoom if args.zoom is not None else zoom_for(west, east, south, north, min(width, height))
    # Fit the extent to the frame aspect: expand the short side, never crop.
    px0, py0 = world_pixels(west, north, zoom)
    px1, py1 = world_pixels(east, south, zoom)
    aspect = width / height
    span_x, span_y = px1 - px0, py1 - py0
    if span_x / span_y < aspect:
        grow = (span_y * aspect - span_x) / 2
        px0, px1 = px0 - grow, px1 + grow
    else:
        grow = (span_x / aspect - span_y) / 2
        py0, py1 = py0 - grow, py1 + grow
    # The mosaic is resampled to the frame, so window pixels map onto frame
    # pixels by a scale that depends only on the window and the frame size --
    # not on whether the mosaic happened to need resizing.
    scale_x, scale_y = width / (px1 - px0), height / (py1 - py0)

    print(f"frames {len(files)}  {width}x{height}  zoom {zoom}  "
          f"extent lon {west:.2f}..{east:.2f} lat {south:.2f}..{north:.2f}", flush=True)

    # 2. Static basemap, fetched once and cached.
    FRAMES.mkdir(exist_ok=True)
    cache = FRAMES / (f"basemap_z{zoom}_{width}x{height}_{west:.2f},{south:.2f},"
                      f"{east:.2f},{north:.2f}.png")
    if cache.exists() and not args.force:
        basemap = np.asarray(Image.open(cache).convert("RGB"))
        print(f"basemap: cached {cache.name}", flush=True)
    else:
        import requests

        started = time.time()
        mosaic = build_mosaic(requests.Session(), zoom, px0, py0, px1, py1)
        rings = draw_boundary(mosaic, geom, zoom, px0, py0)
        if mosaic.size != (width, height):
            mosaic = mosaic.resize((width, height), Image.LANCZOS)
        mosaic.save(cache)
        basemap = np.asarray(mosaic)
        print(f"basemap: {mosaic.size[0]}x{mosaic.size[1]} mosaic + {rings} boundary rings "
              f"in {time.time() - started:.1f}s -> {cache.name}", flush=True)

    # 3. One frame per CSV. Frames are cheap to redraw, so they are never cached:
    #    a leftover frame from a different extent or zoom would be picked up silently.
    dpi = 100
    fig_w, fig_h = width / dpi, height / dpi
    for index, path in enumerate(files, start=1):
        target = FRAMES / f"frame_{index:03d}.png"
        lons, lats = points[path]
        fig = plt.figure(figsize=(fig_w, fig_h), dpi=dpi)
        ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
        ax.set_axis_off()
        # imshow stretches the mosaic across the axes, so a point inside the
        # mosaic window is not yet in output-pixel coordinates. Image row 0 is
        # the north edge and col 0 the west edge; the axes run 0..size.
        ax.imshow(basemap, extent=(0.0, width, height, 0.0), origin="upper",
                  interpolation="antialiased", zorder=0)
        if lons.size:
            sx, sy = world_pixels(lons, lats, zoom)
            ax.scatter((sx - px0) * scale_x, (sy - py0) * scale_y, s=9.0, c=SPOT_HALO,
                       linewidths=0, zorder=2)
            ax.scatter((sx - px0) * scale_x, (sy - py0) * scale_y, s=3.2, c=SPOT_COLOR,
                       linewidths=0, zorder=3)
        ax.text(0.5, 0.975, frame_date(path), transform=ax.transAxes, ha="center", va="top",
                color="white", fontsize=34, fontweight="bold", zorder=4,
                path_effects=[pe.withStroke(linewidth=6, foreground="#101418")])
        ax.text(0.5, 0.012, f"{lons.size:,} fire spots", transform=ax.transAxes, ha="center", va="bottom",
                color="white", fontsize=20, zorder=4,
                path_effects=[pe.withStroke(linewidth=5, foreground="#101418")])
        ax.set_xlim(0, width)
        ax.set_ylim(height, 0)
        fig.savefig(target, dpi=dpi, facecolor="black")
        plt.close(fig)
        print(f"  {index:>2}/{len(files)}  {target.name}  {frame_date(path)}", flush=True)

    # 4. Assemble the GIF: one global palette keeps the basemap identical frame to
    #    frame, so nothing flickers. disposal=1 (leave in place) is required for
    #    PIL to store only the pixels that changed -- disposal=2 forces a full
    #    frame every time and made this 5x larger.
    order = [FRAMES / f"frame_{i:03d}.png" for i in range(1, len(files) + 1)]
    images = [Image.open(p).convert("RGB") for p in order]
    palette = images[0].quantize(colors=256, method=Image.MEDIANCUT, dither=Image.NONE)
    quantised = [im.quantize(palette=palette, dither=Image.FLOYDSTEINBERG) for im in images]
    duration = int(round(1000 / args.fps))
    quantised[0].save(args.out, save_all=True, append_images=quantised[1:],
                      duration=duration, loop=0, optimize=True, disposal=1)
    for im in images:
        im.close()
    print(f"\nwrote {args.out}  {len(quantised)} frames  {duration} ms/frame "
          f"({args.fps:g} fps)  {args.out.stat().st_size / 1e6:.1f} MB", flush=True)
    return


if __name__ == "__main__":
    sys.exit(main())
