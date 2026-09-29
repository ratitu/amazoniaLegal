"""Generate Folium maps for fire data visualization."""
import folium
from folium.plugins import Fullscreen, HeatMap, MarkerCluster, TimestampedGeoJson


def popup_html(idx, row):
    """Generate popup HTML for a fire spot marker."""
    return (
        f"<b>Município:</b> {row['Municipio']}<br>"
        f"<b>Estado:</b> {row.get('Estado', 'N/D')}<br>"
        f"<b>Data:</b> {idx.strftime('%d/%m/%Y %H:%M')}<br>"
        f"<b>Satélite:</b> {row.get('satelite', 'N/D')}<br>"
        f"<b>Bioma:</b> {row.get('bioma', 'N/D')}<br>"
        f"<b>Risco de Fogo:</b> {row.get('risco_fogo', 'N/D')}<br>"
        f"<b>FRP:</b> {row.get('frp', 'N/D')}"
    )


def layer_temporal(df):
    """Create temporal animation layer for fire spots."""
    features = []
    for idx, row in df.iterrows():
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row["Longitude"], row["Latitude"]],
            },
            "properties": {
                "time": idx.strftime("%Y-%m-%dT%H:%M:%S"),
                "popup": popup_html(idx, row),
                "icon": "circle",
                "iconstyle": {
                    "fillColor": "#ff4500",
                    "fillOpacity": 0.8,
                    "stroke": "false",
                    "radius": 6,
                },
            },
        })
    
    tgj = TimestampedGeoJson(
        {"type": "FeatureCollection", "features": features},
        period="PT24H",
        duration="PT0S",
        transition_time=300,
        loop=False,
        auto_play=True,
        add_last_point=True,
    )
    
    return tgj


def plot_mapa(df_filtrado, boundary_geojson, destaque=None, animacao=False, pontos_individuais=False):
    """Generate Folium map with fire spots and Amazonia Legal boundary."""
    if destaque:
        location, zoom = [destaque[0], destaque[1]], 12
    else:
        location, zoom = [-5.0, -55.0], 5
    
    mapa = folium.Map(location=location, zoom_start=zoom)
    
    # Add Amazonia Legal boundary
    if boundary_geojson:
        folium.GeoJson(
            boundary_geojson,
            name="Limites Amazônia Legal",
            style_function=lambda x: {"color": "#228b22", "weight": 2, "fillOpacity": 0.1, "fillColor": "#90ee90"}
        ).add_to(mapa)
    
    if df_filtrado is not None and not df_filtrado.empty:
        # Add ESRI satellite basemap
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri",
            name="Esri Satellite",
            overlay=False,
            control=True,
        ).add_to(mapa)
        
        if pontos_individuais:
            # Individual fire spot markers
            fg = folium.FeatureGroup(name="Focos Individuais")
            for idx, row in df_filtrado.iterrows():
                folium.CircleMarker(
                    location=[row["Latitude"], row["Longitude"]],
                    radius=4,
                    color="#ff4500",
                    fill=True,
                    fillColor="#ff4500",
                    fillOpacity=0.8,
                    popup=folium.Popup(popup_html(idx, row), max_width=300),
                ).add_to(fg)
            fg.add_to(mapa)
        else:
            # Heatmap
            heat_data = df_filtrado[["Latitude", "Longitude"]].values.tolist()
            HeatMap(heat_data, radius=12, name="Mapa de Calor", blur=15).add_to(mapa)
        
        if not pontos_individuais:
            # Marker clusters
            marker_cluster = MarkerCluster(name="Focos de Queimadas")
            for idx, row in df_filtrado.iterrows():
                folium.Marker(
                    location=[row["Latitude"], row["Longitude"]],
                    popup=folium.Popup(popup_html(idx, row), max_width=300),
                    icon=folium.Icon(color="red", icon="fire", icon_color="white"),
                ).add_to(marker_cluster)
            marker_cluster.add_to(mapa)
        
        if animacao:
            layer_temporal(df_filtrado).add_to(mapa)
        
        folium.LayerControl(position="topright").add_to(mapa)
    
    if destaque:
        folium.Marker(
            location=[destaque[0], destaque[1]],
            popup=folium.Popup("Foco selecionado na tabela", max_width=200),
            icon=folium.Icon(color="blue", icon="star", icon_color="white"),
        ).add_to(mapa)
    
    Fullscreen().add_to(mapa)
    
    return mapa
