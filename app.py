"""Streamlit dashboard for Amazonia Legal fire data analysis."""
import streamlit as st
from streamlit_folium import st_folium
from streamlit_option_menu import option_menu
import pandas as pd
import folium

from data_loader import (
    load_data,
    load_boundary,
    calcular_agregacoes,
    df_para_tabela,
    df_resumo_municipios,
    comparar_periodos,
)
from visualizations import (
    fig_diario,
    fig_top_municipios,
    fig_top_estados,
    fig_satelites,
    fig_biomas,
    fig_horario,
    fig_risco,
    fig_comparacao,
)
from advanced_analysis import (
    # Fire Intensity
    fig_frp_distribution,
    fig_frp_by_hour,
    fig_avg_frp_by_municipio,
    high_intensity_stats,
    # Weather & Environmental
    fig_dias_sem_chuva_correlation,
    fig_precipitacao_impact,
    fig_risco_vs_realidade,
    drought_severity_by_municipio,
    # Temporal Patterns
    fig_day_of_week_pattern,
    fig_weekly_rolling_avg,
    peak_fire_days,
    # Biome Analysis
    fig_biome_comparison,
    biome_risk_factors,
    # Satellite Coverage
    fig_satellite_effectiveness,
    # Hotspot Analysis
    fire_recurrence_analysis,
    persistent_fire_zones,
    municipio_risk_classification,
)
from mapping import plot_mapa

# Page config
st.set_page_config(
    page_title="Monitoramento de Queimadas - Amazônia Legal",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown(
    """
    <style>
    div[data-testid="stMetric"] {
        background-color: #1a5f3a;
        padding: 15px;
        border-radius: 10px;
        border: 2px solid #228b22;
        color: white;
        box-shadow: 0px 4px 12px rgba(0,0,0,0.3);
    }
    div[data-testid="stMetricValue"] {
        color: #FFFFFF;
        font-size: 28px;
        font-weight: bold;
    }
    div[data-testid="stMetricLabel"] {
        color: #DDDDDD;
        font-size: 16px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Initialize session state
if "dias" not in st.session_state:
    st.session_state.dias = 27

# Load data
df_queimadas, df_anterior, list_municipios, list_estados, periodo = load_data(st.session_state.dias)
geom, boundary_gdf = load_boundary()
boundary_geojson = boundary_gdf.__geo_interface__

# Calculate aggregations
agg_municipio, agg_estado, agg_diario, agg_bioma, agg_satelite = calcular_agregacoes(df_queimadas)

# Sidebar
with st.sidebar:
    st.markdown("### 🔥 Amazônia Legal")
    st.markdown("**Monitoramento de Queimadas**")
    st.markdown("---")
    
    dias_opcoes = [7, 15, 27, 30]
    if st.session_state.dias not in dias_opcoes:
        st.session_state.dias = 27
    st.selectbox("Período (dias):", dias_opcoes, key="dias")
    
    st.markdown("---")
    
    pagina_alvo = st.session_state.pop("pagina_alvo", None)
    OPCOES = [
        "Início",
        "Evolução Diária",
        "Análise de Intensidade",
        "Análise Ambiental",
        "Padrões Temporais",
        "Análise por Bioma",
        "Cobertura Satelital",
        "Zonas Críticas",
        "Estados e Municípios",
        "Mapa"
    ]
    ICONES = [
        "house",
        "bar-chart",
        "fire",
        "cloud-rain",
        "calendar",
        "tree",
        "satellite",
        "exclamation-triangle",
        "geo-alt",
        "map"
    ]
    
    selected = option_menu(
        menu_title="Navegação",
        options=OPCOES,
        icons=ICONES,
        menu_icon="cast",
        default_index=0,
        manual_select=pagina_alvo,
    )

# Main content
if selected == "Início":
    st.title("🔥 Monitoramento de Queimadas - Amazônia Legal")
    
    st.markdown(
        f"""
        <div style="font-size:15px;">
        
        <p>
        Este painel apresenta o monitoramento de focos de queimadas detectados na 
        <b>Amazônia Legal</b> nos últimos <b>{st.session_state.dias} dias</b>.
        Os dados são provenientes do <b>INPE</b> (Instituto Nacional de Pesquisas Espaciais)
        através do Programa Queimadas.
        </p>
        
        <p>
        Cada foco registra data, hora, município, estado, bioma, satélite e o índice <b>FRP</b>
        (Fire Radiative Power), que estima a intensidade da queima.
        </p>
        
        <ul>
        <li><b>Evolução Diária</b>: Visualização dos focos ao longo do tempo</li>
        <li><b>Análise de Intensidade</b>: FRP, distribuição e intensidade por região</li>
        <li><b>Análise Ambiental</b>: Correlação com chuva e risco de fogo</li>
        <li><b>Padrões Temporais</b>: Análise por dia da semana e tendências</li>
        <li><b>Análise por Bioma</b>: Comparação entre Amazônia e Cerrado</li>
        <li><b>Cobertura Satelital</b>: Efetividade dos satélites de detecção</li>
        <li><b>Zonas Críticas</b>: Áreas de risco e recorrência</li>
        <li><b>Estados e Municípios</b>: Ranking e distribuição por localidade</li>
        <li><b>Mapa</b>: Visualização espacial interativa com heatmap</li>
        </ul>
        
        </div>
        """,
        unsafe_allow_html=True
    )
    
    if df_queimadas is None:
        st.warning(f"Nenhum foco detectado na Amazônia Legal nos últimos {st.session_state.dias} dias.")
    else:
        st.markdown("---")
        st.markdown(f"### Panorama dos últimos {st.session_state.dias} dias")
        
        col1, col2, col3, col4 = st.columns(4)
        
        col1.metric(
            "Total de Focos",
            f"{int(df_queimadas['Número de Focos'].sum()):,}",
            border=True
        )
        
        col2.metric(
            "Municípios",
            f"{len(list_municipios)}",
            border=True
        )
        
        col3.metric(
            "Estados",
            f"{len(list_estados)}",
            border=True
        )
        
        if agg_bioma is not None and not agg_bioma.empty:
            col4.metric(
                "Bioma Principal",
                agg_bioma.idxmax(),
                delta=f"{agg_bioma.max()} focos",
                border=True
            )

elif selected == "Evolução Diária":
    st.title("Evolução Diária dos Focos de Queimadas")
    
    if df_queimadas is None:
        st.warning("Nenhum dado disponível.")
    else:
        st.plotly_chart(fig_diario(agg_diario), use_container_width=True)
        
        st.markdown("### Resumo por município")
        st.dataframe(df_resumo_municipios(df_queimadas), use_container_width=True, hide_index=True)
        
        if "frp" in df_queimadas.columns:
            st.markdown("---")
            st.markdown("### Top 20 Focos por FRP (Intensidade)")
            
            df_frp = pd.DataFrame({
                "Município": df_queimadas["Municipio"].values,
                "Estado": df_queimadas["Estado"].values,
                "Data": df_queimadas.index.strftime("%d/%m/%Y %H:%M").values,
                "FRP": pd.to_numeric(df_queimadas["frp"], errors="coerce").values,
                "Latitude": df_queimadas["Latitude"].values,
                "Longitude": df_queimadas["Longitude"].values,
            })
            df_frp = df_frp.dropna(subset=["FRP"]).sort_values("FRP", ascending=False).head(20).reset_index(drop=True)
            
            event = st.dataframe(
                df_frp,
                on_select="rerun",
                selection_mode="single-row",
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Latitude": None,
                    "Longitude": None,
                    "FRP": st.column_config.NumberColumn("FRP", format="%.1f"),
                }
            )
            
            if event.selection and event.selection.rows:
                sel_row = event.selection.rows[0]
                lat = df_frp.iloc[sel_row]["Latitude"]
                lon = df_frp.iloc[sel_row]["Longitude"]
                mun = df_frp.iloc[sel_row]["Município"]
                
                mapa_frp = folium.Map(location=[lat, lon], zoom_start=10)
                folium.Marker(
                    location=[lat, lon],
                    popup=folium.Popup(f"<b>{mun}</b>", max_width=250),
                    icon=folium.Icon(color="red", icon="fire", icon_color="white")
                ).add_to(mapa_frp)
                st_folium(mapa_frp, use_container_width=True, height=400)

elif selected == "Análise de Intensidade":
    st.title("Análise de Intensidade dos Focos")
    
    if df_queimadas is None:
        st.warning("Nenhum dado disponível.")
    else:
        from advanced_analysis import (
            fig_frp_distribution, fig_frp_by_hour,
            fig_avg_frp_by_municipio, high_intensity_stats
        )
        
        st.markdown("### Distribuição de FRP (Fire Radiative Power)")
        st.plotly_chart(fig_frp_distribution(df_queimadas), use_container_width=True)
        
        st.markdown("---")
        st.markdown("### Intensidade Média por Hora")
        st.plotly_chart(fig_frp_by_hour(df_queimadas), use_container_width=True)
        
        st.markdown("---")
        st.markdown("### Top 20 Municípios por Intensidade Média")
        st.plotly_chart(fig_avg_frp_by_municipio(df_queimadas), use_container_width=True)
        
        st.markdown("---")
        st.markdown("### Estatísticas de Alta Intensidade (FRP > 100)")
        stats = high_intensity_stats(df_queimadas)
        if stats:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Focos de Alta Intensidade", f"{stats['count']}", border=True)
            c2.metric("Percentual do Total", f"{stats['percentage']:.1f}%", border=True)
            c3.metric("FRP Médio", f"{stats['avg_frp']:.1f}", border=True)
            c4.metric("FRP Máximo", f"{stats['max_frp']:.1f}", border=True)

elif selected == "Análise Ambiental":
    st.title("Análise Ambiental e Correlação com Clima")
    
    if df_queimadas is None:
        st.warning("Nenhum dado disponível.")
    else:
        from advanced_analysis import (
            fig_dias_sem_chuva_correlation, fig_precipitacao_impact,
            fig_risco_vs_realidade, drought_severity_by_municipio
        )
        
        st.markdown("### Correlação: Dias Sem Chuva vs Focos")
        st.plotly_chart(fig_dias_sem_chuva_correlation(df_queimadas), use_container_width=True)
        
        st.markdown("---")
        st.markdown("### Impacto da Precipitação")
        st.plotly_chart(fig_precipitacao_impact(df_queimadas), use_container_width=True)
        
        st.markdown("---")
        st.markdown("### Risco Previsto vs Realidade")
        st.plotly_chart(fig_risco_vs_realidade(df_queimadas), use_container_width=True)
        
        st.markdown("---")
        st.markdown("### Top 20 Municípios por Severidade de Seca")
        df_seca = drought_severity_by_municipio(df_queimadas)
        if df_seca is not None and not df_seca.empty:
            st.dataframe(df_seca, use_container_width=True, hide_index=True)

elif selected == "Padrões Temporais":
    st.title("Padrões Temporais dos Focos")
    
    if df_queimadas is None:
        st.warning("Nenhum dado disponível.")
    else:
        from advanced_analysis import (
            fig_day_of_week_pattern, fig_weekly_rolling_avg, peak_fire_days
        )
        
        st.markdown("### Distribuição por Dia da Semana")
        st.plotly_chart(fig_day_of_week_pattern(df_queimadas), use_container_width=True)
        
        st.markdown("---")
        st.markdown("### Média Móvel de 7 Dias")
        st.plotly_chart(fig_weekly_rolling_avg(agg_diario), use_container_width=True)
        
        st.markdown("---")
        st.markdown("### Distribuição por Hora do Dia")
        st.plotly_chart(fig_horario(df_queimadas), use_container_width=True)
        st.caption("Horários em GMT (UTC)")
        
        st.markdown("---")
        st.markdown("### Top 10 Dias com Mais Focos")
        df_pico = peak_fire_days(df_queimadas)
        if df_pico is not None and not df_pico.empty:
            st.dataframe(df_pico, use_container_width=True, hide_index=True)

elif selected == "Análise por Bioma":
    st.title("Análise por Bioma")
    
    if df_queimadas is None:
        st.warning("Nenhum dado disponível.")
    else:
        from advanced_analysis import fig_biome_comparison, biome_risk_factors
        
        st.markdown("### Comparação entre Biomas")
        st.plotly_chart(fig_biome_comparison(df_queimadas), use_container_width=True)
        
        st.markdown("---")
        st.markdown("### Fatores de Risco por Bioma")
        df_risco_bioma = biome_risk_factors(df_queimadas)
        if df_risco_bioma is not None and not df_risco_bioma.empty:
            st.dataframe(df_risco_bioma, use_container_width=True, hide_index=True)
        
        if agg_bioma is not None:
            st.markdown("---")
            st.markdown("### Distribuição de Focos por Bioma")
            st.plotly_chart(fig_biomas(agg_bioma), use_container_width=True)

elif selected == "Cobertura Satelital":
    st.title("Análise de Cobertura Satelital")
    
    if df_queimadas is None:
        st.warning("Nenhum dado disponível.")
    else:
        from advanced_analysis import fig_satellite_effectiveness
        
        st.markdown("### Efetividade dos Satélites")
        st.plotly_chart(fig_satellite_effectiveness(df_queimadas), use_container_width=True)
        
        if agg_satelite is not None:
            st.markdown("---")
            st.markdown("### Distribuição por Satélite")
            st.plotly_chart(fig_satelites(agg_satelite), use_container_width=True)

elif selected == "Zonas Críticas":
    st.title("Análise de Zonas Críticas e Recorrência")
    
    if df_queimadas is None:
        st.warning("Nenhum dado disponível.")
    else:
        from advanced_analysis import (
            fire_recurrence_analysis, persistent_fire_zones,
            municipio_risk_classification
        )
        
        st.markdown("### Análise de Recorrência de Focos")
        df_recorrencia = fire_recurrence_analysis(df_queimadas)
        if df_recorrencia is not None and not df_recorrencia.empty:
            st.markdown("Localizações com focos recorrentes (grade ~1km):")
            st.dataframe(df_recorrencia, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("### Zonas com Focos Persistentes (3+ dias)")
        df_persistente = persistent_fire_zones(df_queimadas)
        if df_persistente is not None and not df_persistente.empty:
            st.dataframe(df_persistente, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("### Classificação de Risco por Município")
        df_risco_mun = municipio_risk_classification(df_queimadas)
        if df_risco_mun is not None and not df_risco_mun.empty:
            st.dataframe(df_risco_mun, use_container_width=True, hide_index=True)

elif selected == "Estados e Municípios":
    st.title("Distribuição por Estado e Município")
    
    if df_queimadas is None:
        st.warning("Nenhum dado disponível.")
    else:
        st.markdown("### Top Estados")
        if agg_estado is not None:
            st.plotly_chart(fig_top_estados(agg_estado), use_container_width=True)
        
        st.markdown("---")
        
        col_sel, _, _ = st.columns([1.2, 2, 1])
        with col_sel:
            num_municipios = st.selectbox("Top municípios:", [10, 20, 30, 50], index=1)
        
        st.plotly_chart(fig_top_municipios(agg_municipio, num_municipios), use_container_width=True)
        
        if agg_satelite is not None:
            st.markdown("---")
            st.plotly_chart(fig_satelites(agg_satelite), use_container_width=True)
        
        if agg_bioma is not None:
            st.markdown("---")
            st.plotly_chart(fig_biomas(agg_bioma), use_container_width=True)

elif selected == "Mapa":
    st.title("Mapa de Calor dos Focos de Queimadas")
    
    col_sel, _, _ = st.columns([1, 2, 1])
    with col_sel:
        if df_queimadas is not None and list_municipios:
            municipios_sel = st.multiselect(
                "Filtrar por município:",
                options=list_municipios,
                default=[],
                key="municipio_map_selector"
            )
        else:
            municipios_sel = []
        
        usar_temporal = st.checkbox("Animação temporal (dia a dia)", key="animacao_temporal")
        focos_individuais = st.checkbox("Exibir focos individualmente", key="focos_individuais", value=False)
    
    if periodo:
        st.markdown(f"**Período:** {periodo[0]} a {periodo[1]}")
    
    df_filtrado = None
    if df_queimadas is not None:
        df_filtrado = df_queimadas
        if municipios_sel:
            df_filtrado = df_queimadas[df_queimadas['Municipio'].isin(municipios_sel)]
    
    mapa = plot_mapa(df_filtrado, boundary_geojson, animacao=usar_temporal, pontos_individuais=focos_individuais)
    st_folium(mapa, use_container_width=True, height=600)
    
    if df_filtrado is not None and not df_filtrado.empty:
        st.markdown("---")
        st.markdown("### Focos Detectados")
        df_pontos = df_para_tabela(df_filtrado)
        st.dataframe(
            df_pontos,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Latitude": None,
                "Longitude": None,
                "FRP": st.column_config.NumberColumn("FRP", format="%.1f"),
            },
        )

# Footer
st.markdown("---")
st.markdown(
    '<p style="text-align:center; font-size:13px; color:#999;">'
    'Dados: INPE/Programa Queimadas · Amazônia Legal 2024'
    '</p>',
    unsafe_allow_html=True
)
