import pandas as pd
from geopy.distance import geodesic
from sklearn.cluster import KMeans
import os
base_dir = os.path.dirname(os.path.abspath(__file__))
poi_file = os.path.join(base_dir, "kerala_poi_recommendations.csv")
poi_df = pd.read_csv(poi_file)

user_location = (8.5241, 76.9366)

def distance_from_user(row, user_loc):
    poi_loc = (row['latitude'], row['longitude'])
    return geodesic(user_loc, poi_loc).km

poi_df['distance_km'] = poi_df.apply(distance_from_user, axis=1, user_loc=user_location)

def recommend_pois(poi_df, top_n=5, categories=None):
    df = poi_df.copy()
    if categories:
        df = df[df['category'].isin(categories)]
    df = df.sort_values(by='distance_km')
    return df.head(top_n)

hotels = recommend_pois(poi_df, top_n=3, categories=['hotel'])
attractions = recommend_pois(poi_df, top_n=2, categories=['attraction'])

recommendations = pd.concat([hotels, attractions])
print("\nRecommended POIs near your booked station:\n")
print(recommendations[['poi_name','category','distance_km']])

def cluster_pois(poi_df, n_clusters=5):
    coords = poi_df[['latitude','longitude']].to_numpy()
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init='auto')
    poi_df['cluster'] = kmeans.fit_predict(coords)
    return poi_df, kmeans

poi_df, kmeans_model = cluster_pois(poi_df)

user_cluster = kmeans_model.predict([user_location])[0]
cluster_pois_df = poi_df[poi_df['cluster']==user_cluster].sort_values(by='distance_km').head(5)

print("\nRecommended POIs based on ML clustering:\n")
print(cluster_pois_df[['poi_name','category','distance_km','cluster']])