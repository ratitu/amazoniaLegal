"""Generate Plotly visualizations for fire data analysis."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from data_loader import CATEGORIAS_RISCO, categoria_risco


def fig_diario(agg_diario, titulo="Focos de Queimadas por Dia"):
    """Daily fire spots chart with 3-day moving average."""
    df_diario = agg_diario.reset_index()
    df_diario["Data"] = df_diario["Data"].dt.strftime("%d/%m")
    
    fig = px.bar(
        df_diario,
        x="Data",
        y="Número de Focos",
        title=titulo,
        color_discrete_sequence=["#ff4500"],
    )
    
    fig.add_trace(go.Scatter(
        x=df_diario["Data"],
        y=df_diario["Número de Focos"].rolling(3, min_periods=1).mean(),
        mode="lines+markers",
        name="Média móvel (3 dias)",
        line=dict(color="#ffa500", width=2),
    ))
    
    fig.update_layout(
        xaxis_title="Data",
        yaxis_title="Número de Focos",
        hoverlabel=dict(font_size=12, font_color="white"),
        hovermode="x unified",
    )
    
    return fig


def fig_top_municipios(agg_municipio, num_municipios, titulo_periodo=""):
    """Top municipalities horizontal bar chart."""
    df_top = (
        agg_municipio.reset_index()
        .sort_values("Número de Focos", ascending=True)
        .tail(num_municipios)
    )
    
    fig = px.bar(
        df_top,
        x="Número de Focos",
        y="Municipio",
        orientation="h",
        title=f"Top {num_municipios} Municípios {titulo_periodo}",
        color_discrete_sequence=["#ff4500"],
        height=600,
    )
    
    fig.update_layout(
        yaxis={"categoryorder": "total ascending"},
        hoverlabel=dict(font_size=12, font_color="white"),
    )
    
    return fig


def fig_top_estados(agg_estado, num_estados=10, titulo="Top Estados"):
    """Top states horizontal bar chart."""
    df_top = (
        agg_estado.reset_index()
        .sort_values("Número de Focos", ascending=True)
        .tail(num_estados)
    )
    
    fig = px.bar(
        df_top,
        x="Número de Focos",
        y="Estado",
        orientation="h",
        title=titulo,
        color_discrete_sequence=["#dc143c"],
        height=500,
    )
    
    fig.update_layout(
        yaxis={"categoryorder": "total ascending"},
        hoverlabel=dict(font_size=12, font_color="white"),
    )
    
    return fig


def fig_satelites(agg_satelite, titulo="Focos Detectados por Satélite", altura=400):
    """Satellite distribution chart."""
    df_sat = (
        agg_satelite.reset_index()
        .sort_values("Número de Focos", ascending=True)
    )
    
    fig = px.bar(
        df_sat,
        x="Número de Focos",
        y="satelite",
        orientation="h",
        title=titulo,
        color_discrete_sequence=["#ff8c00"],
        height=altura,
    )
    
    fig.update_layout(hoverlabel=dict(font_size=12, font_color="white"))
    
    return fig


def fig_biomas(agg_bioma, titulo="Focos por Bioma", altura=300):
    """Biome distribution chart."""
    df_bio = (
        agg_bioma.reset_index()
        .sort_values("Número de Focos", ascending=True)
    )
    
    fig = px.bar(
        df_bio,
        x="Número de Focos",
        y="bioma",
        orientation="h",
        title=titulo,
        color_discrete_sequence=["#8b0000"],
        height=altura,
    )
    
    fig.update_layout(hoverlabel=dict(font_size=12, font_color="white"))
    
    return fig


def fig_horario(df):
    """Hourly distribution chart."""
    horas = df.index.hour.value_counts().sort_index()
    df_h = pd.DataFrame({"Hora": horas.index, "Número de Focos": horas.values})
    
    fig = px.bar(
        df_h,
        x="Hora",
        y="Número de Focos",
        title="Focos por Hora do Dia (GMT)",
        color_discrete_sequence=["#ff4500"],
    )
    
    fig.update_layout(
        xaxis=dict(dtick=1),
        xaxis_title="Hora (GMT)",
        yaxis_title="Número de Focos",
        hoverlabel=dict(font_size=12, font_color="white"),
    )
    
    return fig


def fig_risco(df):
    """Fire risk category distribution."""
    if "risco_fogo" not in df.columns:
        return None
    
    categorias = df["risco_fogo"].apply(categoria_risco)
    agg = df.groupby(categorias)["Número de Focos"].sum().reset_index()
    agg.columns = ["Categoria de Risco", "Número de Focos"]
    agg = agg[agg["Categoria de Risco"].isin(CATEGORIAS_RISCO)]
    
    fig = px.bar(
        agg,
        x="Número de Focos",
        y="Categoria de Risco",
        orientation="h",
        title="Focos por Categoria de Risco de Fogo",
        color_discrete_sequence=["#8b0000"],
        height=300,
        category_orders={"Categoria de Risco": CATEGORIAS_RISCO},
    )
    
    fig.update_layout(
        xaxis_title="Número de Focos",
        yaxis_title=None,
        hoverlabel=dict(font_size=12, font_color="white"),
    )
    
    return fig


def fig_comparacao(serie_atual, serie_anterior, label_atual, label_anterior):
    """Period comparison chart."""
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=serie_atual.index,
        y=serie_atual.values,
        mode="lines+markers",
        name=label_atual,
        line=dict(color="#ff4500", width=2),
    ))
    
    fig.add_trace(go.Scatter(
        x=serie_anterior.index,
        y=serie_anterior.values,
        mode="lines+markers",
        name=label_anterior,
        line=dict(color="gray", width=2, dash="dash"),
    ))
    
    fig.update_layout(
        title="Focos por Dia — Período Atual vs Período Anterior",
        xaxis_title="Data",
        yaxis_title="Número de Focos",
        hoverlabel=dict(font_size=12, font_color="white"),
        hovermode="x unified",
    )
    
    return fig
