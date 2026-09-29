# AGENTS.md — Amazônia Legal Fire Dashboard

## Run the app

```bash
cd /home/ratitu/Documents/claude/amazoniaLegal
source venv/bin/activate
streamlit run app.py
```

Default port: 8501. No env vars needed.

## Environment

- Python venv at `./venv/` — always activate before running or installing
- Pinned deps in `requirements.txt` — install with `pip install -r requirements.txt`
- No CI, no tests, no linter configured
- **`requirements.txt` is dashboard-only.** `make_gif.py`, `verify_clip.py`, and
  `verify_gif.py` import `matplotlib` and `Pillow`, which are NOT pinned. Install
  them separately before running the GIF pipeline or either verifier.
- `verify_clip.py` shells out to GDAL/OGR for one of its checks, so `gdal` must
  be on PATH.

## Verification

`python verify_clip.py` and `python verify_gif.py` are the only checks in the
repo — there is no test suite. Run them after touching `clip_focos.py`,
`make_gif.py`, or the boundary file.

## Architecture

Single-page Streamlit app split into 4 modules:

| File | Role |
|------|------|
| `app.py` | Entry point, sidebar, routing to 10 pages |
| `data_loader.py` | CSV loading, GeoDataFrame creation, aggregations |
| `visualizations.py` | Basic Plotly charts |
| `advanced_analysis.py` | High/medium priority analysis functions |
| `mapping.py` | Folium map with heatmap + temporal animation |

## Data

- **Input**: `clipped/focos_diario_br_YYYYMMDD.csv` — 27 files, 515,683 rows total
- **Raw**: `raw/` — same 27 files unclipped, 688,368 rows. Regenerate `clipped/` with `python clip_focos.py`
- **Boundary**: `Limites_Amazonia_Legal_2024.geojson` (EPSG:4326)
- `clip_focos.py` passes rows through as raw strings, so original column formatting survives
- `load_data(dias=27)` loads the N most recent files by filename sort order

## Known gotcha: Streamlit widget + session state

Never pass `index=` to a `st.selectbox` that also uses `key=` when the key already exists in `st.session_state`. It throws a warning and may crash on Streamlit 1.58.

**Pattern used here** (correct):
```python
if "dias" not in st.session_state:
    st.session_state.dias = 27
st.selectbox("Período (dias):", [7, 15, 27, 30], key="dias")
```

## Pages (navigation order)

1. Início — overview metrics
2. Evolução Diária — daily bar chart + moving average
3. Análise de Intensidade — FRP distribution
4. Análise Ambiental — rain correlation
5. Padrões Temporais — weekday/rolling avg
6. Análise por Bioma — Amazônia vs Cerrado
7. Cobertura Satelital — satellite effectiveness
8. Zonas Críticas — recurrence + hotspot
9. Estados e Municípios — top rankings
10. Mapa — Folium heatmap + animation

## Data columns (lowercase after load)

`id, lat, lon, data_hora_gmt, satelite, municipio, estado, pais, municipio_id, estado_id, pais_id, numero_dias_sem_chuva, precipitacao, risco_fogo, bioma, frp`

`risco_fogo` is a float 0–1; categorized as Baixo/Médio/Alto/Crítico by `categoria_risco()`. Value `-999` = no data.

## Caching

All data-loading functions use `@st.cache_data(ttl=3600)`. During development, clear cache with the Streamlit menu or restart the server.
