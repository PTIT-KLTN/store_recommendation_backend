import requests
import math
from datetime import datetime
from database.mongodb import MongoDBConnection
from bson import ObjectId
import os

class LocationService:
    def __init__(self):
        self.openroute_api_key = os.getenv('OPENROUTE_API_KEY')
        self.base_url = "https://api.openrouteservice.org"
        self.db = MongoDBConnection.get_primary_db()
        self.metadata_db = MongoDBConnection.get_metadata_db()
    
    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculate the great circle distance between two points 
        on the earth (specified in decimal degrees) using Haversine formula
        Returns distance in kilometers
        """
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Radius of earth in kilometers
        r = 6371
        return c * r
    
    def find_nearby_stores(self, latitude, longitude, radius_km=10, limit=10):
        """
        Find nearby stores using OpenRoute Service API
        Returns list of nearby stores with distances
        """
        try:
            stores_collection = self.metadata_db.stores.find({})  
            print(f"🔍 Searching for stores near ({latitude}, {longitude}) within {radius_km} km")          
            nearby_stores = []
            for store in stores_collection:
                if 'latitude' not in store or 'longitude' not in store:
                    continue
                distance = self.calculate_distance(
                    latitude, longitude,
                    store['latitude'], store['longitude']
                )
                
                if distance <= radius_km:
                    store_with_distance = store.copy()
                    store_with_distance['distance_km'] = round(distance, 2)
                    nearby_stores.append(store_with_distance)
                    
            # Sort by distance
            nearby_stores.sort(key=lambda x: x['distance_km'])
            
            # Return limited results
            result = nearby_stores[:limit]
            print(f"  📤 Returning {len(result)} stores")
            
            return result
            
        except Exception as e:
            print(f"🔍 ERROR in find_nearby_stores: {e}")
            return []

    def get_route_info(self, start_lat, start_lng, end_lat, end_lng):
        """
        Get route information between two points using OpenRoute Service
        """
        if not self.openroute_api_key:
            return None
            
        try:
            url = f"{self.base_url}/v2/directions/driving-car"
            
            headers = {
                'Authorization': self.openroute_api_key,
                'Content-Type': 'application/json'
            }
            
            data = {
                'coordinates': [[start_lng, start_lat], [end_lng, end_lat]],
                'format': 'json'
            }
            
            response = requests.post(url, json=data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                route_data = response.json()
                if route_data.get('routes'):
                    route = route_data['routes'][0]
                    summary = route.get('summary', {})
                    
                    return {
                        'distance_meters': summary.get('distance', 0),
                        'duration_seconds': summary.get('duration', 0),
                        'distance_km': round(summary.get('distance', 0) / 1000, 2),
                        'duration_minutes': round(summary.get('duration', 0) / 60, 1)
                    }
            
            return None
            
        except Exception as e:
            print(f"Error getting route info: {e}")
            return None
    
    def update_user_near_stores(self, user_id, location, force_refresh=False):
        """
        Update near stores for a specific user
        """
        try:
            latitude = location['latitude']
            longitude = location['longitude']
            
            # Find nearby stores
            nearby_stores = self.find_nearby_stores(latitude, longitude)

            # Enhanced store data with route information
            enhanced_stores = []
            for store in nearby_stores:
                enhanced_store = store.copy()
                
                # Get route info if OpenRoute API is available
                route_info = self.get_route_info(
                    latitude, longitude,
                    store['latitude'], store['longitude']
                )
                
                if route_info:
                    enhanced_store['route_info'] = route_info
                
                enhanced_store['updated_at'] = datetime.utcnow()
                enhanced_stores.append(enhanced_store)
            
            # Update user's near_stores
            self.db.users.update_one(
                {'_id': ObjectId(user_id)},
                {
                    '$set': {
                        'near_stores': enhanced_stores,
                        'near_stores_updated_at': datetime.utcnow()
                    }
                }
            )
            
            print(f"Updated near stores for user {user_id}: {len(enhanced_stores)} stores found")
            return enhanced_stores
            
        except Exception as e:
            print(f"Error updating near stores for user {user_id}: {e}")
            return []
    
    def geocode_address(self, address):
        """
        Convert address to coordinates using OpenRoute Service
        """
        if not self.openroute_api_key:
            return None
            
        try:
            url = f"{self.base_url}/geocode/search"
            
            params = {
                'api_key': self.openroute_api_key,
                'text': address,
                'size': 1
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('features'):
                    feature = data['features'][0]
                    coordinates = feature['geometry']['coordinates']
                    
                    return {
                        'longitude': coordinates[0],
                        'latitude': coordinates[1],
                        'address': feature['properties'].get('label', address)
                    }
            
            return None
            
        except Exception as e:
            print(f"Error geocoding address: {e}")
            return None

location_service = LocationService()