import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import plotly.express as px
from pathlib import Path

# --- Configuration & Setup ---
st.set_page_config(
    page_title="SafeYield: Wildfire Risk Dashboard",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
    <style>
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;
        color: #1f77b4;
    }
    .metric-label {
        font-size: 14px;
        color: #666;
    }
    </style>
""", unsafe_allow_html=True)

PROCESSED_DIR = Path('Data/processed')
PORTUGAL_GEOJSON = "https://raw.githubusercontent.com/johan/world.geo.json/master/countries/PRT.geo.json"

# --- Data Loading ---
@st.cache_data
def load_data():
    fires = pd.read_csv(PROCESSED_DIR / 'processed_fires.csv')
    housing = pd.read_csv(PROCESSED_DIR / 'processed_housing.csv')
    impact = pd.read_csv(PROCESSED_DIR / 'zone_impact.csv')
    
    # Ensure datetime format for fires
    fires['Timestamp'] = pd.to_datetime(fires['Timestamp'])
    fires['Year'] = fires['Timestamp'].dt.year
    
    return fires, housing, impact

try:
    df_fires, df_housing, df_impact = load_data()
except FileNotFoundError:
    st.error("Processed data not found. Please run `python data_pipeline.py` first.")
    st.stop()

# --- Sidebar Filters ---
st.sidebar.title("🔥 SafeYield Controls")

st.sidebar.header("Temporal Filter")
min_year = int(df_fires['Year'].min())
max_year = int(df_fires['Year'].max())
selected_years = st.sidebar.slider("Select Year Range:", min_value=min_year, max_value=max_year, value=(min_year, max_year))

st.sidebar.header("Geographic Filter")
districts = ["All"] + sorted(df_fires['District'].dropna().unique().tolist())
selected_district = st.sidebar.selectbox("Select District:", districts)

st.sidebar.header("Risk Filter")
min_risk = float(df_impact['risk_scaled'].min())
max_risk = float(df_impact['risk_scaled'].max())
selected_risk = st.sidebar.slider("Minimum Risk Level:", min_value=min_risk, max_value=max_risk, value=min_risk, step=0.05)

# --- Apply Filters ---
filtered_fires = df_fires[(df_fires['Year'] >= selected_years[0]) & (df_fires['Year'] <= selected_years[1])]
if selected_district != "All":
    filtered_fires = filtered_fires[filtered_fires['District'] == selected_district]

filtered_impact = df_impact[df_impact['risk_scaled'] >= selected_risk].copy()
filtered_impact['risk_str'] = filtered_impact['risk_scaled'].map('{:.2f}'.format)
filtered_impact['price_int_str'] = filtered_impact['price_int'].map('{:,.0f}'.format)
filtered_impact['price_adj_str'] = filtered_impact['price_adjusted'].map('{:,.0f}'.format)
filtered_impact['gap_pct'] = ((filtered_impact['price_int'] - filtered_impact['price_adjusted']) / filtered_impact['price_int']) * 100
filtered_impact['gap_str'] = filtered_impact['gap_pct'].map('{:.1f}%'.format)

filtered_zones = filtered_impact['zone'].tolist()
filtered_housing = df_housing[df_housing['zone'].isin(filtered_zones)]

# --- App Layout: Tabs ---
tab1, tab2, tab3 = st.tabs(["🗺️ Wildfire History", "💰 Risk-Adjusted Valuation", "📊 Analysis & Rankings"])

# --- Tab 1: Wildfire History ---
with tab1:
    st.title("Historical Wildfire Events (1980 - 2021)")
    st.markdown("Interactive map of fire events. The radius and color intensity reflect the burned area in hectares.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Total Fire Events</div><div class="metric-value">{len(filtered_fires):,}</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Total Burned Area (ha)</div><div class="metric-value">{filtered_fires["Burned_Area"].sum():,.0f}</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Avg Event Size (ha)</div><div class="metric-value">{filtered_fires["Burned_Area"].mean():,.1f}</div></div>', unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)

    # Calculate optimal radius scale based on zoom level and data size
    if not filtered_fires.empty:
        # Scale for pydeck point radius
        filtered_fires['radius'] = np.sqrt(filtered_fires['Burned_Area'].clip(lower=1)) * 50

        # PyDeck map
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=filtered_fires[['Longitude', 'Latitude', 'Burned_Area', 'radius', 'Year', 'Municipality']],
            get_position='[Longitude, Latitude]',
            get_radius='radius',
            get_fill_color='[200 + (Burned_Area/10), 50, 50, 140]',
            pickable=True,
            auto_highlight=True,
        )

        view_state = pdk.ViewState(
            longitude=-8.2245,
            latitude=39.3999,
            zoom=5.5,
            pitch=0,
        )

        geojson_layer = pdk.Layer(
            "GeoJsonLayer",
            PORTUGAL_GEOJSON,
            opacity=0.3,
            stroked=True,
            filled=True,
            extruded=False,
            get_fill_color="[220, 220, 220, 100]",
            get_line_color="[150, 150, 150, 200]",
            get_line_width=2000,
        )

        r = pdk.Deck(
            layers=[geojson_layer, layer],
            initial_view_state=view_state,
            tooltip={"text": "{Municipality} ({Year})\nBurned Area: {Burned_Area} ha"},
            map_style='mapbox://styles/mapbox/light-v10'
        )
        st.pydeck_chart(r)
    else:
        st.warning("No fire events found for the selected filters.")

# --- Tab 2: Risk-Adjusted Valuation ---
with tab2:
    st.title("Risk-Adjusted Real Estate Valuation")
    st.markdown("Exploring the 200 spatial zones. Market prices are discounted based on the localized composite SafeYield Risk Index.")

    if not filtered_impact.empty:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Map of zones
            layer = pdk.Layer(
                "ScatterplotLayer",
                data=filtered_impact,
                get_position='[longitude, latitude]',
                get_radius=8000,
                get_fill_color='[255 * risk_scaled, 50, 200 * (1 - risk_scaled), 160]',
                pickable=True,
                auto_highlight=True,
            )

            view_state = pdk.ViewState(
                longitude=-8.2245,
                latitude=39.3999,
                zoom=5.8,
                pitch=30,
            )

            geojson_layer = pdk.Layer(
                "GeoJsonLayer",
                PORTUGAL_GEOJSON,
                opacity=0.1,
                stroked=True,
                filled=True,
                extruded=False,
                get_fill_color="[50, 50, 50, 50]",
                get_line_color="[100, 100, 100, 150]",
                get_line_width=2000,
            )

            r = pdk.Deck(
                layers=[geojson_layer, layer],
                initial_view_state=view_state,
                tooltip={
                    "html": "<b>Zone ID:</b> {zone}<br/><b>Risk Index:</b> {risk_str}<br/><b>Market Price:</b> €{price_int_str}<br/><b>Adjusted Price:</b> €{price_adj_str}<br/><b>Discount:</b> {gap_str}",
                    "style": {"color": "white"}
                },
                map_style='mapbox://styles/mapbox/dark-v10'
            )
            st.pydeck_chart(r)

        with col2:
            st.subheader("Valuation Summary")
            avg_gap = filtered_impact['gap_pct'].mean()
            max_gap = filtered_impact['gap_pct'].max()
            st.metric("Avg Valuation Discount", f"{avg_gap:.1f}%")
            st.metric("Max Valuation Discount", f"{max_gap:.1f}%")
            st.markdown("---")
            st.dataframe(
                filtered_impact[['zone', 'risk_scaled', 'price_int', 'price_adjusted', 'gap_pct']]
                .sort_values('risk_scaled', ascending=False)
                .head(10)
                .style.format({
                    'risk_scaled': '{:.2f}',
                    'price_int': '€{:,.0f}',
                    'price_adjusted': '€{:,.0f}',
                    'gap_pct': '{:.1f}%'
                }),
                use_container_width=True
            )
    else:
         st.warning("No zones match the current risk filter threshold.")

# --- Tab 3: Analysis & Rankings ---
with tab3:
    st.title("Market Analysis & Wildfire Trends")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Top Districts by Burned Area")
        top_districts = (
            df_fires.dropna(subset=['District'])
            .groupby('District')
            .agg(total_burned=('Burned_Area', 'sum'))
            .sort_values('total_burned', ascending=False)
            .head(10)
            .reset_index()
        )
        fig1 = px.bar(
            top_districts, x='total_burned', y='District', orientation='h',
            title="Cumulative Burned Area (1980-2021)",
            labels={'total_burned': 'Total Burned (ha)', 'District': ''},
            color='total_burned', color_continuous_scale='YlOrRd'
        )
        fig1.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        st.subheader("Burned Area Over Time")
        yearly_fires = df_fires.groupby('Year').agg(total_burned=('Burned_Area', 'sum')).reset_index()
        fig2 = px.line(
            yearly_fires, x='Year', y='total_burned',
            title="Annual Wildfire Intensity",
            labels={'total_burned': 'Total Burned (ha)', 'Year': 'Year'},
            markers=True
        )
        fig2.update_traces(line_color='firebrick')
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    st.subheader("Valuation Discount by Zone (Ranked by Risk)")
    impact_sorted = df_impact.sort_values('risk_scaled').reset_index(drop=True)
    impact_sorted['gap_eur'] = impact_sorted['price_int'] - impact_sorted['price_adjusted']

    col_gap1, col_gap2 = st.columns(2)
    with col_gap1:
        fig3 = px.area(
            impact_sorted, x=impact_sorted.index, y='gap_eur',
            labels={'gap_eur': 'Discount (€)', 'index': 'Zones (Sorted by Risk)'},
            title="Valuation Discount (€) across 200 Zones"
        )
        fig3.update_traces(fillcolor='rgba(178, 34, 34, 0.3)', line_color='firebrick')
        st.plotly_chart(fig3, use_container_width=True)
    with col_gap2:
        fig4 = px.area(
            impact_sorted, x=impact_sorted.index, y='gap_pct',
            labels={'gap_pct': 'Discount (%)', 'index': 'Zones (Sorted by Risk)'},
            title="Valuation Discount (%) across 200 Zones"
        )
        fig4.update_traces(fillcolor='rgba(178, 34, 34, 0.3)', line_color='firebrick')
        st.plotly_chart(fig4, use_container_width=True)
