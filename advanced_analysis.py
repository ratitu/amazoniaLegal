"""Advanced analysis functions for fire data."""
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from data_loader import categoria_risco, CATEGORIAS_RISCO


# ============================================================================
# Fire Intensity Analysis
# ============================================================================

def fig_frp_distribution(df):
    """FRP distribution histogram."""
    if "frp" not in df.columns:
        return None
    
    frp_values = pd.to_numeric(df["frp"], errors="coerce").dropna()
    
    fig = px.histogram(
        frp_values,
        nbins=50,
        title="Distribuição de FRP (Fire Radiative Power)",
        labels={"value": "FRP", "count": "Número de Focos"},
        color_discrete_sequence=["#ff4500"],
    )
    
    fig.update_layout(
        xaxis_title="FRP",
        yaxis_title="Número de Focos",
        hoverlabel=dict(font_size=12, font_color="white"),
        showlegend=False,
    )
    
    return fig


def fig_frp_by_hour(df):
    """Average FRP by hour of day."""
    if "frp" not in df.columns:
        return None
    
    df_copy = df.copy()
    df_copy["hora"] = df_copy.index.hour
    df_copy["frp_numeric"] = pd.to_numeric(df_copy["frp"], errors="coerce")
    
    hourly_avg = df_copy.groupby("hora")["frp_numeric"].mean().reset_index()
    hourly_avg.columns = ["Hora", "FRP Médio"]
    
    fig = px.bar(
        hourly_avg,
        x="Hora",
        y="FRP Médio",
        title="Intensidade Média por Hora do Dia",
        color_discrete_sequence=["#dc143c"],
    )
    
    fig.update_layout(
        xaxis=dict(dtick=1),
        xaxis_title="Hora (GMT)",
        yaxis_title="FRP Médio",
        hoverlabel=dict(font_size=12, font_color="white"),
    )
    
    return fig


def fig_avg_frp_by_municipio(df, top_n=20):
    """Average FRP by municipality."""
    if "frp" not in df.columns:
        return None
    
    df_copy = df.copy()
    df_copy["frp_numeric"] = pd.to_numeric(df_copy["frp"], errors="coerce")
    
    avg_frp = (
        df_copy.groupby("Municipio")["frp_numeric"]
        .mean()
        .sort_values(ascending=True)
        .tail(top_n)
        .reset_index()
    )
    avg_frp.columns = ["Município", "FRP Médio"]
    
    fig = px.bar(
        avg_frp,
        x="FRP Médio",
        y="Município",
        orientation="h",
        title=f"Top {top_n} Municípios por Intensidade Média (FRP)",
        color_discrete_sequence=["#8b0000"],
        height=600,
    )
    
    fig.update_layout(
        yaxis={"categoryorder": "total ascending"},
        hoverlabel=dict(font_size=12, font_color="white"),
    )
    
    return fig


def high_intensity_stats(df, threshold=100):
    """Statistics for high-intensity fires."""
    if "frp" not in df.columns:
        return None
    
    df_copy = df.copy()
    df_copy["frp_numeric"] = pd.to_numeric(df_copy["frp"], errors="coerce")
    
    high_intensity = df_copy[df_copy["frp_numeric"] > threshold]
    
    stats = {
        "total_high_intensity": len(high_intensity),
        "percentage": (len(high_intensity) / len(df_copy)) * 100,
        "avg_frp": high_intensity["frp_numeric"].mean(),
        "max_frp": high_intensity["frp_numeric"].max(),
        "top_municipios": high_intensity["Municipio"].value_counts().head(10).to_dict(),
    }
    
    return stats


# ============================================================================
# Weather & Environmental Correlation
# ============================================================================

def fig_dias_sem_chuva_correlation(df):
    """Correlation between days without rain and fire frequency."""
    if "numero_dias_sem_chuva" not in df.columns:
        return None
    
    df_copy = df.copy()
    df_copy["dias_sem_chuva"] = pd.to_numeric(df_copy["numero_dias_sem_chuva"], errors="coerce")
    
    # Group by days without rain
    correlation = (
        df_copy.groupby("dias_sem_chuva")["Número de Focos"]
        .sum()
        .reset_index()
        .sort_values("dias_sem_chuva")
    )
    
    fig = px.scatter(
        correlation,
        x="dias_sem_chuva",
        y="Número de Focos",
        title="Correlação: Dias Sem Chuva vs. Número de Focos",
        trendline="ols",
        color_discrete_sequence=["#ff4500"],
    )
    
    fig.update_layout(
        xaxis_title="Dias Sem Chuva",
        yaxis_title="Número de Focos",
        hoverlabel=dict(font_size=12, font_color="white"),
    )
    
    return fig


def fig_precipitacao_impact(df):
    """Impact of precipitation on fire occurrence."""
    if "precipitacao" not in df.columns:
        return None
    
    df_copy = df.copy()
    df_copy["precip"] = pd.to_numeric(df_copy["precipitacao"], errors="coerce")
    df_copy["tem_chuva"] = df_copy["precip"].apply(lambda x: "Com Chuva" if x > 0 else "Sem Chuva")
    
    rain_impact = df_copy.groupby("tem_chuva")["Número de Focos"].sum().reset_index()
    
    fig = px.bar(
        rain_impact,
        x="tem_chuva",
        y="Número de Focos",
        title="Impacto da Precipitação nos Focos de Queimadas",
        color_discrete_sequence=["#4682b4"],
        height=400,
    )
    
    fig.update_layout(
        xaxis_title="Condição",
        yaxis_title="Número de Focos",
        hoverlabel=dict(font_size=12, font_color="white"),
    )
    
    return fig


def fig_risco_vs_realidade(df):
    """Compare predicted risk with actual fire occurrence."""
    if "risco_fogo" not in df.columns:
        return None
    
    df_copy = df.copy()
    df_copy["categoria_risco"] = df_copy["risco_fogo"].apply(categoria_risco)
    
    risk_reality = (
        df_copy.groupby("categoria_risco")["Número de Focos"]
        .sum()
        .reindex(CATEGORIAS_RISCO, fill_value=0)
        .reset_index()
    )
    risk_reality.columns = ["Categoria de Risco", "Número de Focos"]
    
    fig = px.bar(
        risk_reality,
        x="Categoria de Risco",
        y="Número de Focos",
        title="Risco Previsto vs. Ocorrência Real",
        color_discrete_sequence=["#ff8c00"],
        category_orders={"Categoria de Risco": CATEGORIAS_RISCO},
    )
    
    fig.update_layout(
        xaxis_title="Categoria de Risco",
        yaxis_title="Número de Focos",
        hoverlabel=dict(font_size=12, font_color="white"),
    )
    
    return fig


def drought_severity_by_municipio(df, top_n=20):
    """Municipalities with most severe drought (days without rain)."""
    if "numero_dias_sem_chuva" not in df.columns:
        return None
    
    df_copy = df.copy()
    df_copy["dias_sem_chuva"] = pd.to_numeric(df_copy["numero_dias_sem_chuva"], errors="coerce")
    
    drought = (
        df_copy.groupby("Municipio")
        .agg({
            "dias_sem_chuva": "mean",
            "Número de Focos": "sum"
        })
        .sort_values("dias_sem_chuva", ascending=False)
        .head(top_n)
        .reset_index()
    )
    drought.columns = ["Município", "Média Dias Sem Chuva", "Total de Focos"]
    
    return drought


# ============================================================================
# Temporal Patterns
# ============================================================================

def fig_day_of_week_pattern(df):
    """Fire frequency by day of week."""
    df_copy = df.copy()
    df_copy["dia_semana"] = df_copy.index.day_name()
    
    # Portuguese day names
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_translation = {
        "Monday": "Segunda",
        "Tuesday": "Terça",
        "Wednesday": "Quarta",
        "Thursday": "Quinta",
        "Friday": "Sexta",
        "Saturday": "Sábado",
        "Sunday": "Domingo"
    }
    
    weekly = df_copy.groupby("dia_semana")["Número de Focos"].sum().reindex(day_order).reset_index()
    weekly["dia_semana_pt"] = weekly["dia_semana"].map(day_translation)
    
    fig = px.bar(
        weekly,
        x="dia_semana_pt",
        y="Número de Focos",
        title="Focos por Dia da Semana",
        color_discrete_sequence=["#ff4500"],
    )
    
    fig.update_layout(
        xaxis_title="Dia da Semana",
        yaxis_title="Número de Focos",
        hoverlabel=dict(font_size=12, font_color="white"),
    )
    
    return fig


def fig_weekly_rolling_avg(df, window=7):
    """Weekly rolling average of fire spots."""
    weekly = df.resample("D")["Número de Focos"].sum()
    rolling = weekly.rolling(window=window, min_periods=1).mean()
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=weekly.index,
        y=weekly.values,
        mode="markers",
        name="Focos Diários",
        marker=dict(color="#ff4500", size=4),
        opacity=0.5,
    ))
    
    fig.add_trace(go.Scatter(
        x=rolling.index,
        y=rolling.values,
        mode="lines",
        name=f"Média Móvel ({window} dias)",
        line=dict(color="#ffa500", width=3),
    ))
    
    fig.update_layout(
        title=f"Tendência Semanal (Média Móvel de {window} Dias)",
        xaxis_title="Data",
        yaxis_title="Número de Focos",
        hoverlabel=dict(font_size=12, font_color="white"),
        hovermode="x unified",
    )
    
    return fig


def peak_fire_days(df, top_n=10):
    """Identify and analyze worst fire days."""
    daily = df.resample("D")["Número de Focos"].sum().sort_values(ascending=False).head(top_n)
    
    peak_days = pd.DataFrame({
        "Data": daily.index.strftime("%d/%m/%Y"),
        "Número de Focos": daily.values
    })
    
    return peak_days


# ============================================================================
# Biome-Specific Analysis
# ============================================================================

def fig_biome_comparison(df):
    """Side-by-side biome comparison."""
    if "bioma" not in df.columns:
        return None
    
    biome_stats = df.groupby("bioma").agg({
        "Número de Focos": "sum",
        "Municipio": "nunique",
        "satelite": "nunique",
    }).reset_index()
    biome_stats.columns = ["Bioma", "Total Focos", "Municípios", "Satélites"]
    
    # Create subplots
    from plotly.subplots import make_subplots
    
    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=("Total de Focos", "Municípios Afetados", "Satélites Detectores")
    )
    
    for i, col in enumerate(["Total Focos", "Municípios", "Satélites"], start=1):
        fig.add_trace(
            go.Bar(x=biome_stats["Bioma"], y=biome_stats[col], name=col,
                   marker_color="#228b22" if i == 1 else "#8b4513" if i == 2 else "#4682b4"),
            row=1, col=i
        )
    
    fig.update_layout(
        title_text="Comparação entre Biomas",
        showlegend=False,
        height=400,
    )
    
    return fig


def biome_risk_factors(df):
    """Different risk patterns per biome."""
    if "bioma" not in df.columns or "risco_fogo" not in df.columns:
        return None
    
    df_copy = df.copy()
    df_copy["categoria_risco"] = df_copy["risco_fogo"].apply(categoria_risco)
    
    biome_risk = df_copy.groupby(["bioma", "categoria_risco"])["Número de Focos"].sum().reset_index()
    
    fig = px.bar(
        biome_risk,
        x="bioma",
        y="Número de Focos",
        color="categoria_risco",
        title="Distribuição de Risco por Bioma",
        category_orders={"categoria_risco": CATEGORIAS_RISCO},
        barmode="group",
    )
    
    fig.update_layout(
        xaxis_title="Bioma",
        yaxis_title="Número de Focos",
        hoverlabel=dict(font_size=12, font_color="white"),
    )
    
    return fig


# ============================================================================
# Satellite Coverage Analysis
# ============================================================================

def fig_satellite_effectiveness(df):
    """Detection rates by satellite."""
    if "satelite" not in df.columns:
        return None
    
    sat_stats = df.groupby("satelite").agg({
        "Número de Focos": "sum",
        "Municipio": "nunique",
    }).reset_index()
    sat_stats.columns = ["Satélite", "Total Detectado", "Cobertura (Municípios)"]
    sat_stats = sat_stats.sort_values("Total Detectado", ascending=True)
    
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Focos Detectados", "Cobertura Municipal")
    )
    
    fig.add_trace(
        go.Bar(y=sat_stats["Satélite"], x=sat_stats["Total Detectado"],
               orientation="h", marker_color="#ff8c00"),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Bar(y=sat_stats["Satélite"], x=sat_stats["Cobertura (Municípios)"],
               orientation="h", marker_color="#4682b4"),
        row=1, col=2
    )
    
    fig.update_layout(
        title_text="Efetividade dos Satélites",
        showlegend=False,
        height=500,
    )
    
    return fig


# ============================================================================
# Hotspot Analysis
# ============================================================================

def fire_recurrence_analysis(df):
    """Locations with repeated fires."""
    # Round coordinates to ~1km grid
    df_copy = df.copy()
    df_copy["lat_grid"] = (df_copy["Latitude"] * 100).round() / 100
    df_copy["lon_grid"] = (df_copy["Longitude"] * 100).round() / 100
    df_copy["grid_cell"] = df_copy["lat_grid"].astype(str) + "," + df_copy["lon_grid"].astype(str)
    
    recurrence = df_copy.groupby("grid_cell").agg({
        "Número de Focos": "sum",
        "Latitude": "first",
        "Longitude": "first",
        "Municipio": "first",
    }).reset_index()
    recurrence = recurrence[recurrence["Número de Focos"] > 1].sort_values("Número de Focos", ascending=False)
    recurrence.columns = ["Grid", "Focos Recorrentes", "Latitude", "Longitude", "Município"]
    
    return recurrence


def persistent_fire_zones(df, min_days=3):
    """Areas burning continuously across multiple days."""
    df_copy = df.copy()
    df_copy["lat_grid"] = (df_copy["Latitude"] * 100).round() / 100
    df_copy["lon_grid"] = (df_copy["Longitude"] * 100).round() / 100
    df_copy["grid_cell"] = df_copy["lat_grid"].astype(str) + "," + df_copy["lon_grid"].astype(str)
    df_copy["date"] = df_copy.index.date
    
    persistent = df_copy.groupby("grid_cell").agg({
        "date": lambda x: x.nunique(),
        "Número de Focos": "sum",
        "Latitude": "first",
        "Longitude": "first",
        "Municipio": "first",
    }).reset_index()
    
    persistent = persistent[persistent["date"] >= min_days].sort_values("date", ascending=False)
    persistent.columns = ["Grid", "Dias Ativos", "Total Focos", "Latitude", "Longitude", "Município"]
    
    return persistent


def municipio_risk_classification(df):
    """Classify municipalities by fire history."""
    risk_scores = df.groupby("Municipio").agg({
        "Número de Focos": "sum",
        "frp": lambda x: pd.to_numeric(x, errors="coerce").mean() if "frp" in df.columns else 0,
    }).reset_index()
    
    risk_scores["score"] = risk_scores["Número de Focos"] * 0.7 + risk_scores["frp"] * 0.3
    risk_scores["classificação"] = pd.qcut(
        risk_scores["score"],
        q=3,
        labels=["Risco Baixo", "Risco Médio", "Risco Alto"],
        duplicates="drop"
    )
    
    risk_scores = risk_scores.sort_values("score", ascending=False)
    risk_scores.columns = ["Município", "Total Focos", "FRP Médio", "Score", "Classificação"]
    
    return risk_scores
