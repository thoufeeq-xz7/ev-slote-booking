import pandas as pd
from geopy.distance import geodesic
import os
import logging

logger = logging.getLogger(__name__)

def distance_from_user(row, user_loc):
    poi_loc = (row['latitude'], row['longitude'])
    return geodesic(user_loc, poi_loc).km

def recommend_pois_by_category(poi_df, top_n=5, categories=None):
    df = poi_df.copy()
    if categories:
        df = df[df['category'].isin(categories)]
    
    if df.empty:
        return pd.DataFrame()

    df = df.sort_values(by='distance_km')
    return df.head(top_n)

def get_recommendations_for_station(station_latitude, station_longitude, poi_file_path):
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_dir, "kerala_poi_recommendations.csv") # Use the literal filename here

    if not os.path.exists(full_path):
        logger.error(f"FATAL: POI recommendation file not found at: {full_path}")
        return pd.DataFrame()

    try:
        poi_df = pd.read_csv(full_path)
    except Exception as e:
        logger.error(f"Error loading POI file from {full_path}: {e}")
        return pd.DataFrame()

    user_location = (float(station_latitude), float(station_longitude))
    
    poi_df['distance_km'] = poi_df.apply(distance_from_user, axis=1, user_loc=user_location)

    # Only recommend hotels (top 3 closest)
    hotels = recommend_pois_by_category(poi_df, top_n=3, categories=['hotel'])
    if hotels.empty:
        logger.warning("No hotels found near this station. Returning fallback POI.")
        fallback_df = poi_df.sort_values(by='distance_km').head(1)
        fallback_df['category'] = 'General (Fallback)'
        return fallback_df[['poi_name', 'category', 'distance_km']]
    return hotels[['poi_name', 'category', 'distance_km']]