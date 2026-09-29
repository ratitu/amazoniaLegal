"""Load and process Amazonia Legal fire data from clipped CSV files."""
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import geopandas as gpd
import shapely
import streamlit as st

BASE = Path(__file__).resolve().parent
CLIPPED = BASE / "clipped"
BOUNDARY = BASE / "Limites_Amazonia_Legal_2024.geojson"

CATEGORIAS_RISCO = ["Baixo", "Médio", "Alto", "Crítico", "Sem dado"]


def load_boundary():
    """Load Amazonia Legal boundary geometry."""
    gdf = gpd.read_file(BOUNDARY)
    geom = shapely.union_all(gdf.geometry)
    if not geom.is_valid:
        geom = geom.buffer(0)
    return geom, gdf


def categoria_risco(v):
    """Categorize fire risk value."""
    if pd.isna(v) or v == -999:
        return "Sem dado"
    if v <= 0.25:
        return "Baixo"
    if v <= 0.50:
        return "Médio"
    if v <= 0.75:
        return "Alto"
    return "Crítico"


@st.cache_data(ttl=3600)
def load_data(dias=27):
    """Load fire data from clipped CSV files."""
    files = sorted(CLIPPED.glob("focos_diario_br_*.csv"))
    
    if not files:
        return None, None, None, None, None
    
    # Load most recent N days
    files = files[-dias:] if len(files) > dias else files
    
    registros = []
    for file in files:
        try:
            df = pd.read_csv(file, dtype=str, keep_default_na=False)
            df.columns = [c.strip().lower() for c in df.columns]
            registros.append(df)
        except Exception:
            continue
    
    if not registros:
        return None, None, None, None, None
    
    df = pd.concat(registros, ignore_index=True)
    
    # Parse coordinates
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df = df.dropna(subset=["lat", "lon"])
    
    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs="EPSG:4326",
    )
    
    # Prepare data
    gdf["Data"] = pd.to_datetime(gdf["data_hora_gmt"], errors="coerce")
    gdf = gdf.dropna(subset=["Data"])
    gdf.set_index("Data", inplace=True)
    gdf["Número de Focos"] = 1
    gdf["Latitude"] = gdf["lat"]
    gdf["Longitude"] = gdf["lon"]
    gdf["Municipio"] = gdf["municipio"]
    gdf["Estado"] = gdf["estado"]
    
    if gdf.empty:
        return None, None, None, None, None
    
    # Split into current and previous periods
    hoje = datetime.now()
    data_corte = hoje - timedelta(days=dias)
    df_atual = gdf[gdf.index > data_corte]
    df_anterior = gdf[gdf.index <= data_corte]
    
    if df_atual.empty:
        df_atual = gdf
        df_anterior = None
    
    list_municipios = sorted(df_atual["Municipio"].unique())
    list_estados = sorted(df_atual["Estado"].unique())
    data_inicio = df_atual.index.min().strftime("%d/%m/%Y")
    data_fim = df_atual.index.max().strftime("%d/%m/%Y")
    
    return df_atual, df_anterior, list_municipios, list_estados, (data_inicio, data_fim)


def calcular_agregacoes(df):
    """Calculate aggregations for the dataframe."""
    if df is None:
        return None, None, None, None, None
    
    agg_municipio = df.groupby("Municipio")["Número de Focos"].sum()
    agg_estado = df.groupby("Estado")["Número de Focos"].sum()
    agg_diario = df.resample("D")["Número de Focos"].sum()
    agg_bioma = df.groupby("bioma")["Número de Focos"].sum() if "bioma" in df.columns else None
    agg_satelite = df.groupby("satelite")["Número de Focos"].sum() if "satelite" in df.columns else None
    
    return agg_municipio, agg_estado, agg_diario, agg_bioma, agg_satelite


def df_para_tabela(df):
    """Convert dataframe to table format for display."""
    df_pontos = pd.DataFrame({
        "Data": df.index.strftime("%d/%m/%Y %H:%M").values,
        "Município": df["Municipio"].values,
        "Estado": df["Estado"].values,
    })
    
    for nome, col in [("Satélite", "satelite"), ("Bioma", "bioma"),
                      ("Risco de Fogo", "risco_fogo"), ("FRP", "frp")]:
        if col in df.columns:
            df_pontos[nome] = df[col].values
    
    df_pontos["Latitude"] = df["Latitude"].values
    df_pontos["Longitude"] = df["Longitude"].values
    
    return df_pontos


def df_resumo_municipios(df):
    """Generate municipality summary."""
    return df.groupby("Municipio").agg({
        "Número de Focos": "sum",
        "satelite": lambda x: x.nunique() if x.notna().any() else 0,
    }).rename(columns={"satelite": "Satélites"}).reset_index().sort_values(
        "Número de Focos", ascending=False
    )


def comparar_periodos(df_atual, df_anterior):
    """Compare current and previous periods."""
    if df_anterior is None or df_anterior.empty:
        return None
    
    atual = df_atual.groupby("Municipio")["Número de Focos"].sum()
    anterior = df_anterior.groupby("Municipio")["Número de Focos"].sum()
    comparacao = pd.DataFrame({"Atual": atual, "Anterior": anterior}).fillna(0)
    comparacao["Variação"] = comparacao["Atual"] - comparacao["Anterior"]
    
    return comparacao.sort_values("Variação", ascending=False)
