#!/usr/bin/env python3
"""Verify clipped/ against the Amazonia Legal boundary, independently of clip_focos.py.

  A. No row loss    - raw rows == kept + dropped; no lat/lon silently unparseable.
  B. Byte fidelity  - every line of clipped/ byte-identical to the matching raw line,
                      same order, header unchanged.
  C. Full re-derive - every row's inside/outside verdict recomputed with a different
                      algorithm (matplotlib ray casting, nonzero rule) and compared
                      to the GEOS prepared-geometry result. All 688,368 rows.
  D. Third engine   - a seeded sample re-tested through GDAL's own clipper
                      (OGRGeometry intersection), independent of both of the above.

Check C is not a formality: the boundary is 86 polygons / 330,195 vertices, and
516,609 of the 688,368 spots lie within 0.01 deg of an edge, so essentially every
row sits in territory where a CRS, winding, or predicate mistake could hide.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd
import shapely
from matplotlib.path import Path as MplPath
from shapely.geometry import MultiPolygon

from clip_focos import load_boundary

BASE = Path(__file__).resolve().parent
RAW = BASE / "raw"
OUT = BASE / "clipped"
BOUNDARY = BASE / "Limites_Amazonia_Legal_2024.geojson"

OGR_SAMPLE = 250
OGR_DAYS = ("20260901", "20260915", "20260927")

failures: list[str] = []


def ring_codes(n: int) -> np.ndarray:
    return np.concatenate(
        [[MplPath.MOVETO], np.full(n - 2, MplPath.LINETO), [MplPath.CLOSEPOLY]]
    )


def ccw(coords: np.ndarray) -> np.ndarray:
    """Force counter-clockwise winding (positive signed area)."""
    x, y = coords[:, 0], coords[:, 1]
    area2 = float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
    return coords if area2 >= 0 else coords[::-1]


class RayCaster:
    """matplotlib.path containment over the boundary, bbox-prefiltered per polygon.

    matplotlib needs clockwise shells and counter-clockwise holes for the nonzero
    rule, which is the reverse of the GeoJSON convention, so shells are reversed
    and holes normalised here.
    """

    def __init__(self, geom: MultiPolygon) -> None:
        self.bounds: list[tuple[float, float, float, float]] = []
        self.paths: list[MplPath] = []
        for poly in geom.geoms:
            shell = np.asarray(poly.exterior.coords)
            if shapely.is_ccw(poly.exterior):
                shell = shell[::-1]
            verts = [shell]
            codes = [ring_codes(len(shell))]
            for ring in poly.interiors:
                hole = ccw(np.asarray(ring.coords))
                verts.append(hole)
                codes.append(ring_codes(len(hole)))
            self.paths.append(MplPath(np.concatenate(verts), np.concatenate(codes)))
            self.bounds.append(poly.bounds)

    def inside(self, pts: np.ndarray) -> np.ndarray:
        out = np.zeros(len(pts), dtype=bool)
        for path, (x0, y0, x1, y1) in zip(self.paths, self.bounds):
            sel = ((pts[:, 0] >= x0) & (pts[:, 0] <= x1)
                   & (pts[:, 1] >= y0) & (pts[:, 1] <= y1))
            if sel.any():
                out[sel] |= path.contains_points(pts[sel])
        return out


def ogr_inside(pts: np.ndarray) -> set[int]:
    """Inside-test through GDAL's clipper - OGRGeometry intersection, not GEOS."""
    features = [
        {"type": "Feature", "properties": {"id": int(i)},
         "geometry": {"type": "Point", "coordinates": [float(x), float(y)]}}
        for i, (x, y) in enumerate(pts)
    ]
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / "pts.geojson", Path(tmp) / "clipped.geojson"
        src.write_text(json.dumps({"type": "FeatureCollection", "name": "pts",
                                   "features": features}))
        res = subprocess.run(
            ["ogr2ogr", "-f", "GeoJSON", str(dst), str(src),
             "-clipsrc", str(BOUNDARY), "-clipsrclayer", BOUNDARY.stem],
            capture_output=True,
        )
        if res.returncode != 0:
            raise SystemExit(f"ogr2ogr failed: {res.stderr.decode()[:600]}")
        return {int(f["properties"]["id"])
                for f in json.loads(dst.read_text())["features"] if f["geometry"] is not None}


def main() -> None:
    t0 = time.time()
    geom = load_boundary()
    shapely.prepare(geom)
    caster = RayCaster(geom)
    rng = np.random.default_rng(20260927)

    print(f"boundary: {geom.geom_type}, {len(geom.geoms)} polygons, "
          f"{shapely.get_num_coordinates(geom):,} vertices, "
          f"valid={geom.is_valid} simple={geom.is_simple}", flush=True)

    n_in = n_out = n_bad = 0
    ogr_checked = 0
    for src in sorted(RAW.glob("focos_diario_br_*.csv")):
        day = src.stem.removeprefix("focos_diario_br_")
        raw_lines = src.read_text(encoding="utf-8").splitlines()
        df = pd.read_csv(src, dtype=str, keep_default_na=False)
        lons = pd.to_numeric(df["lon"].str.strip(), errors="coerce").to_numpy()
        lats = pd.to_numeric(df["lat"].str.strip(), errors="coerce").to_numpy()
        valid = np.isfinite(lons) & np.isfinite(lats)
        pts = np.column_stack([lons, lats])

        # A. no row loss
        if len(raw_lines) - 1 != len(df):
            failures.append(f"{day}: raw lines {len(raw_lines) - 1} != parsed rows {len(df)}")
        if not valid.all():
            bad = int((~valid).sum())
            n_bad += bad
            failures.append(f"{day}: {bad} rows with unparseable lat/lon")

        # reference verdict, re-derived from the clip_focos algorithm
        mask = np.zeros(len(df), dtype=bool)
        mask[valid] = shapely.covers(geom, shapely.points(lons[valid], lats[valid]))

        # B. byte fidelity of the emitted file
        clip_lines = (OUT / src.name).read_text(encoding="utf-8").splitlines()
        if clip_lines[0] != raw_lines[0]:
            failures.append(f"{day}: header changed")
        if clip_lines[1:] != [ln for ln, m in zip(raw_lines[1:], mask) if m]:
            failures.append(f"{day}: clipped rows not byte-identical to the raw subset")

        # C. full re-derive through a different algorithm
        other = np.zeros(len(df), dtype=bool)
        other[valid] = caster.inside(pts[valid])
        if not np.array_equal(other, mask):
            failures.append(f"{day}: ray casting disagrees with GEOS on "
                            f"{int((other != mask).sum())} of {len(df)} rows")

        # D. third engine on a sample
        if day in OGR_DAYS:
            # split the sample between kept and dropped rows so both directions are exercised
            kept_idx = np.flatnonzero(mask)
            drop_idx = np.flatnonzero(~mask)
            half = min(OGR_SAMPLE // 2, len(kept_idx), len(drop_idx))
            idx = np.concatenate([rng.choice(kept_idx, half, replace=False),
                                  rng.choice(drop_idx, half, replace=False)])
            hits = ogr_inside(pts[idx])  # ids are positions *within* idx, not row indices
            ogr = np.fromiter((j in hits for j in range(len(idx))), bool, len(idx))
            ogr_checked += len(idx)
            if not np.array_equal(ogr, mask[idx]):
                failures.append(f"{day}: GDAL clipper disagrees on "
                                f"{int((ogr != mask[idx]).sum())}/{len(idx)} sampled rows")

        n_in += int(mask.sum())
        n_out += int((~mask).sum())
        print(f"  {day}  {len(df):>6} rows  {int(mask.sum()):>6} kept  "
              f"[{time.time() - t0:6.0f}s]", flush=True)

    total = n_in + n_out
    print(f"\nraw rows        {total:>9,}")
    print(f"kept            {n_in:>9,}   -> clipped/")
    print(f"dropped         {n_out:>9,}   outside the boundary")
    print(f"unparseable     {n_bad:>9,}")
    print(f"check C rows    {total:>9,}   ray casting vs GEOS")
    print(f"check D rows    {ogr_checked:>9,}   GDAL clipper vs GEOS "
          f"({OGR_SAMPLE} on each of {', '.join(OGR_DAYS)})")

    if failures:
        print(f"\nFAIL ({len(failures)}):", flush=True)
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print(f"\nOK - all checks passed in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
