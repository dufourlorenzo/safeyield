import warnings
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler, MinMaxScaler
import os

warnings.filterwarnings('ignore')

# Configuration
DATA_DIR = Path('Data')
PROCESSED_DIR = Path('Data/processed')
FIRE_PATH = DATA_DIR / 'all_data_ptcontinental_1980_2021.csv'
GEO_PATH = DATA_DIR / 'concelhos_centroids_mainland_table.csv'
HOUSES_PATH = DATA_DIR / 'portugal_houses.csv'
LISTINGS_PATH = DATA_DIR / 'portugal_listinigs.csv'

N_ZONES = 200
MAX_DISCOUNT = 0.20
RISK_WEIGHTS = {
    'fire_count': 0.4,
    'total_burned': 0.4,
    'avg_burned': 0.2,
}

def run_pipeline():
    print("Creating processed directory...")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("1. Loading and processing wildfire data...")
    fires_raw = pd.read_csv(FIRE_PATH)
    geo_admin = pd.read_csv(GEO_PATH, usecols=['NAME_1', 'NAME_2', 'ID_1', 'ID_2'])

    df_fires = (
        fires_raw
        .merge(geo_admin, left_on='Concelho', right_on='NAME_2', how='left')
        .drop(columns=['NAME_2'])
        .rename(columns={
            'Concelho': 'Municipality',
            'Mês': 'Month',
            'Ano': 'Year',
            'Área': 'Burned_Area',
            'lon': 'Longitude',
            'lat': 'Latitude',
            'datetime': 'Timestamp',
            'NAME_1': 'District',
            'ID_1': 'District_ID',
            'ID_2': 'Municipality_ID',
        })
    )
    df_fires['Timestamp'] = pd.to_datetime(df_fires['Timestamp'])
    df_fires = df_fires.dropna(subset=['Latitude', 'Longitude'])

    print("2. Loading and processing real estate data...")
    houses = pd.read_csv(HOUSES_PATH)
    listings = pd.read_csv(LISTINGS_PATH)

    houses = houses.loc[:, houses.isnull().mean() < 0.25]
    listings = listings.loc[:, listings.isnull().mean() < 0.25]

    listings_city = (
        listings
        .groupby('City', as_index=False)['Price']
        .median()
    )

    houses['location'] = houses['location'].astype(str).str.lower().str.strip()
    listings_city['City'] = listings_city['City'].astype(str).str.lower().str.strip()

    df_housing = (
        houses
        .merge(listings_city, left_on='location', right_on='City', how='left')
        .dropna(subset=['price_int'])
    )

    num_cols = df_housing.select_dtypes(include=np.number).columns
    df_housing[num_cols] = df_housing[num_cols].fillna(df_housing[num_cols].median())

    print("3. Spatial zoning (K-Means, k=200)...")
    geo_scaler = StandardScaler()
    house_coords = geo_scaler.fit_transform(df_housing[['latitude', 'longitude']].to_numpy())

    kmeans = KMeans(n_clusters=N_ZONES, random_state=42, n_init=10)
    df_housing['zone'] = kmeans.fit_predict(house_coords)

    fire_coords = geo_scaler.transform(df_fires[['Latitude', 'Longitude']].to_numpy())
    df_fires['zone'] = kmeans.predict(fire_coords)

    print("4. Calculating Risk Index per zone...")
    zone_stats = (
        df_fires
        .groupby('zone')
        .agg(
            fire_count=('Burned_Area', 'count'),
            total_burned=('Burned_Area', 'sum'),
            avg_burned=('Burned_Area', 'mean'),
        )
        .reset_index()
        .fillna(0)
    )

    scaler_metrics = MinMaxScaler()
    metric_cols = list(RISK_WEIGHTS.keys())
    zone_stats[metric_cols] = scaler_metrics.fit_transform(zone_stats[metric_cols])

    zone_stats['risk_index'] = sum(
        w * zone_stats[m] for m, w in RISK_WEIGHTS.items()
    )

    print("5. Calculating risk-adjusted valuation...")
    zone_prices = df_housing.groupby('zone', as_index=False)['price_int'].mean()

    impact_df = (
        zone_prices
        .merge(zone_stats[['zone', 'risk_index']], on='zone', how='left')
        .fillna(0)
    )
    impact_df['risk_scaled'] = impact_df['risk_index'] / impact_df['risk_index'].max()
    impact_df['price_adjusted'] = impact_df['price_int'] * (1 - MAX_DISCOUNT * impact_df['risk_scaled'])
    impact_df['gap_pct'] = ((impact_df['price_int'] - impact_df['price_adjusted']) / impact_df['price_int']) * 100
    
    # Merge coords back for mapping zones
    zone_coords = df_housing.groupby('zone', as_index=False)[['latitude', 'longitude']].mean()
    impact_df = impact_df.merge(zone_coords, on='zone', how='left')

    print("6. Saving processed datasets...")
    # Using CSV for broad compatibility without needing pyarrow/fastparquet
    df_fires.to_csv(PROCESSED_DIR / 'processed_fires.csv', index=False)
    df_housing.to_csv(PROCESSED_DIR / 'processed_housing.csv', index=False)
    impact_df.to_csv(PROCESSED_DIR / 'zone_impact.csv', index=False)

    print("Data pipeline completed successfully!")

if __name__ == '__main__':
    run_pipeline()