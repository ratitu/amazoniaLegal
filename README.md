# Amazônia Legal — Fire Dashboard

Streamlit dashboard for fire-spot detection in the Amazônia Legal region, plus an
offline pipeline that clips the raw INPE data and renders it as a timelapse GIF.

## Run the dashboard

```bash
source venv/bin/activate
streamlit run app.py
```

Opens on http://localhost:8501. No environment variables required.

## Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` covers the dashboard only. The GIF pipeline additionally needs
`matplotlib` and `Pillow`, which are **not** pinned there:

```bash
pip install matplotlib pillow
```

## Data

| | |
|---|---|
| Raw input | `raw/focos_diario_br_20260901.csv` … `20260927.csv` — 27 files, 688,368 rows |
| Dashboard input | `clipped/` — same 27 files, 515,683 rows (inside the boundary only) |
| Boundary | `Limites_Amazonia_Legal_2024.geojson` (EPSG:4326) |
| Source | [INPE / Programa Queimadas](https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/diario/Brasil/) |

Columns (lowercased on load):

```
id, lat, lon, data_hora_gmt, satelite, municipio, estado, pais,
municipio_id, estado_id, pais_id, numero_dias_sem_chuva,
precipitacao, risco_fogo, bioma, frp
```

`risco_fogo` is a float 0–1 (`-999` means no data), bucketed into
Baixo / Médio / Alto / Crítico by `categoria_risco()`.

## Pipeline

```bash
python clip_focos.py     # raw/ -> clipped/, rows kept verbatim
python make_gif.py       # clipped/ -> focos_timelapse.gif, 2 fps
```

`clip_focos.py` passes rows through as raw strings, so the original column
formatting survives the round trip. Points exactly on the boundary are kept.

`make_gif.py` options:

```
--input DIR    directory of daily CSVs (default: clipped/)
--out FILE     output GIF (default: focos_timelapse.gif)
--size WxH     frame size in pixels (default: 1600x1200)
--zoom N       tile zoom (default: highest that fills the frame)
--fps N        frames per second (default: 2.0)
--force        rebuild the cached basemap and frames
```

The ESRI World Imagery basemap mosaic and the boundary outline are static, so
they are fetched once and cached as `frames/basemap_z*_*.png`. Only the fire
spots are re-plotted per frame. Frames are cached too — pass `--force` after
changing input, size, or zoom.

## Verification

```bash
python verify_clip.py    # checks clipped/ against the boundary
python verify_gif.py     # checks the rendered GIF
```

`verify_clip.py` checks four things: no row is lost, every clipped line is
byte-identical to its raw counterpart in the same order, all 688,368 rows are
re-derived with an independent algorithm (matplotlib ray casting) and compared
against the GEOS result, and a seeded sample is re-tested through GDAL's own
clipper. The independence matters here — the boundary is 86 polygons with
330,195 vertices, and 516,609 of the 688,368 spots sit within 0.01° of an edge,
so nearly every row is in territory where a CRS, winding-order, or predicate
mistake would hide.

`verify_gif.py` measures instead of viewing: spots must land on the pixels the
Mercator math predicts, survive GIF quantisation and delta encoding, and differ
between consecutive frames.

## Dashboard pages

| # | Page | Contents |
|---|------|----------|
| 1 | Início | Total spots, municipality/state counts, primary biome |
| 2 | Evolução Diária | Daily counts + 3-day moving average, municipality table, top 20 by FRP |
| 3 | Análise de Intensidade | FRP histogram, mean FRP by hour, high-intensity statistics |
| 4 | Análise Ambiental | Days-without-rain correlation, precipitation impact, predicted risk vs actual, drought severity |
| 5 | Padrões Temporais | Day-of-week pattern, 7-day rolling average, peak days |
| 6 | Análise por Bioma | Amazônia vs Cerrado side by side, risk factors per biome |
| 7 | Cobertura Satelital | Detection rate and coverage per satellite |
| 8 | Zonas Críticas | Recurrence grid, persistent zones (3+ days), municipality risk classes |
| 9 | Estados e Municípios | Top states, top municipalities (10/20/30/50), satellite and biome distribution |
| 10 | Mapa | Folium heatmap, optional markers, day-by-day animation, municipality filter, boundary overlay |

The period selector in the sidebar (7 / 15 / 27 / 30 days) reloads everything
and is cached for one hour.

## Project structure

```
app.py                 Streamlit entry point, sidebar, page routing
data_loader.py         CSV loading, GeoDataFrame construction, aggregations
visualizations.py      Basic Plotly charts
advanced_analysis.py   Intensity, environmental, temporal, biome, satellite, hotspot
mapping.py             Folium map and temporal animation
clip_focos.py          raw/ -> clipped/ boundary clip
make_gif.py            clipped/ -> timelapse GIF
verify_clip.py         Clip correctness checks
verify_gif.py          GIF correctness checks
clipped/               27 clipped CSVs
raw/                   27 unclipped CSVs
frames/                Cached basemap and rendered frames
focos_timelapse.gif    Rendered output
```

## Notes

- All data-loading functions use `@st.cache_data(ttl=3600)`. Clear it from the
  Streamlit menu or restart the server after adding new CSV files.
- `load_data(dias)` takes the N most recent files by filename sort order, so the
  filename date stamp is what defines the window.
- The Folium animation is a `TimestampedGeoJson` layer and needs a
  JavaScript-capable browser.
- FRP (Fire Radiative Power) estimates fire intensity from the radiative flux
  detected by the sensor.

## Data licence

Data: INPE / Programa Queimadas. Dashboard code is project-local.
