#!/usr/bin/env python3
"""Clip INPE daily fire-spot CSVs to the Amazonia Legal boundary.

Reads raw/focos_diario_br_YYYYMMDD.csv (WGS84, lat/lon columns) and writes
clipped/focos_diario_br_YYYYMMDD.csv keeping only spots inside or exactly on
the Amazonia Legal polygon. Rows are carried through as raw strings so the
original column formatting survives the round trip.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import Polygon

BASE = Path(__file__).resolve().parent
RAW = BASE / "raw"
OUT = BASE / "clipped"
BOUNDARY = BASE / "Limites_Amazonia_Legal_2024.geojson"
EXPECTED_EPSG = 4326


def load_boundary() -> Polygon:
    """Union the boundary features into one prepared-ready geometry."""
    gdf = gpd.read_file(BOUNDARY)
    if gdf.crs is None or gdf.crs.to_epsg() != EXPECTED_EPSG:
        raise SystemExit(f"boundary CRS must be EPSG:{EXPECTED_EPSG}, got {gdf.crs}")
    geom = shapely.union_all(gdf.geometry)
    if not geom.is_valid:
        geom = geom.buffer(0)
    return geom


def inside_mask(df: pd.DataFrame, geom: Polygon) -> np.ndarray:
    """True where the spot falls inside or on the boundary."""
    lons = pd.to_numeric(df["lon"].str.strip(), errors="coerce").to_numpy()
    lats = pd.to_numeric(df["lat"].str.strip(), errors="coerce").to_numpy()
    valid = np.isfinite(lons) & np.isfinite(lats)
    mask = np.zeros(len(df), dtype=bool)
    if valid.any():
        mask[valid] = shapely.covers(geom, shapely.points(lons[valid], lats[valid]))
    return mask


def main() -> None:
    OUT.mkdir(exist_ok=True)
    geom = load_boundary()
    shapely.prepare(geom)  # ~30k-vertex boundary: prepare once, reuse for every day
    print(f"boundary: EPSG:{EXPECTED_EPSG}, {geom.geom_type}, {shapely.get_num_coordinates(geom):,} vertices")

    files = sorted(RAW.glob("focos_diario_br_*.csv"))
    if not files:
        raise SystemExit(f"no source files in {RAW}")

    total_in = total_seen = 0
    for src in files:
        df = pd.read_csv(src, dtype=str, keep_default_na=False)
        kept = df.loc[inside_mask(df, geom)]
        kept.to_csv(OUT / src.name, index=False)
        total_seen += len(df)
        total_in += len(kept)
        print(f"{src.name}  {len(df):>6} -> {len(kept):>6}  ({100 * len(kept) / len(df):5.1f}%)")

    print(f"\nTOTAL {total_seen:,} spots -> {total_in:,} inside Amazonia Legal "
          f"({100 * total_in / total_seen:.1f}%)")


if __name__ == "__main__":
    main()
