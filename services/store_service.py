from database.mongodb import MongoDBConnection
from bson import ObjectId
from datetime import datetime
from services.location_service import location_service

metadata_db = MongoDBConnection.get_metadata_db()
primary_db = MongoDBConnection.get_primary_db()

def get_all_stores_data(page, size, pattern, store_name, chain, store_location):
    """Lấy danh sách stores từ metadata_db"""
    skip = page * size
    
    query_conditions = []

    if pattern:
        pattern_regex = {'$regex': pattern, '$options': 'i'}
        query_conditions.append({
            '$or': [
                {'store_name': pattern_regex},
                {'chain': pattern_regex},
                {'store_location': pattern_regex}
            ]
        })
    
    if store_name:
        query_conditions.append({ 'store_name': {'$regex': store_name, '$options': 'i'} })
    
    if chain:
        query_conditions.append({ 'chain': {'$regex': f'^{chain}$', '$options': 'i'} })
    
    if store_location:
        query_conditions.append({ 'store_location': {'$regex': store_location, '$options': 'i'} })
    
    if query_conditions:
        if len(query_conditions) == 1:
            query = query_conditions[0]
        else:
            query = {'$and': query_conditions}
    else:
        query = {}
    
    stores = list(
        metadata_db.stores.find(query)
        .sort([('store_name', 1), ('chain', 1)])
        .skip(skip)
        .limit(size)
    )
    
    total = metadata_db.stores.count_documents(query)
    
    # Convert ObjectId to string
    for store in stores:
        if '_id' in store:
            store['_id'] = str(store['_id'])
    
    # Calculate pagination info
    total_pages = (total + size - 1) // size if size > 0 else 0
    has_next = page < total_pages - 1
    has_prev = page > 0
    
    return {
        'stores': stores,
        'total_stores': total,
        'pagination': {
            'current_page': page,
            'page_size': size,
            'total_pages': total_pages,
            'total_elements': total,
            'has_next': has_next,
            'has_previous': has_prev
        },
        'filters': {
            'pattern': pattern,
            'store_name': store_name,
            'chain': chain,
            'store_location': store_location
        }
    }

def get_store_by_id_data(store_id):
    """Lấy chi tiết store theo store_id"""
    try:
        store = metadata_db.stores.find_one({'store_id': store_id})

        if not store:
            try:
                store_id_int = int(store_id)
                store = metadata_db.stores.find_one({'store_id': store_id_int})
            except ValueError:
                pass
        
        if not store:
            try:
                store = metadata_db.stores.find_one({'_id': ObjectId(store_id)})
            except:
                pass

        if not store:
            return None, "Store not found"
        
        # Convert ObjectId to string
        if '_id' in store:
            store['_id'] = str(store['_id'])
        
        # Add additional computed fields
        store['has_coordinates'] = 'latitude' in store and 'longitude' in store
        store['rating_info'] = {
            'total_score': store.get('totalScore', 0),
            'reviews_count': store.get('reviewsCount', 0),
            'average_rating': round(store.get('totalScore', 0) / max(store.get('reviewsCount', 1), 1), 2)
        }
        
        return store, None
        
    except Exception as e:
        return None, str(e)

def get_store_suggestions_data(query, limit, suggestion_type='all'):
    """Tạo store search suggestions"""
    regex_pattern = {'$regex': f'^{query}', '$options': 'i'}
    contains_pattern = {'$regex': query, '$options': 'i'}
    
    suggestions = []
    
    # Store name suggestions
    if suggestion_type in ['all', 'store_name']:
        name_matches = metadata_db.stores.find(
            {'store_name': regex_pattern},
            {'store_name': 1, 'chain': 1, 'store_location': 1, 'store_id': 1}
        ).limit(limit // 2 if suggestion_type == 'all' else limit)
        
        for store in name_matches:
            suggestions.append({
                'text': store.get('store_name', ''),
                'type': 'store_name',
                'store_id': store.get('store_id'),
                'chain': store.get('chain', ''),
                'location': store.get('store_location', ''),
                'display_text': f"{store.get('store_name', '')} - {store.get('chain', '')}"
            })
    
    # Chain suggestions
    if suggestion_type in ['all', 'chain'] and len(suggestions) < limit:
        remaining_limit = limit - len(suggestions)
        chain_matches = metadata_db.stores.find(
            {'chain': regex_pattern},
            {'chain': 1, 'store_name': 1, 'store_location': 1, 'store_id': 1}
        ).limit(remaining_limit)
        
        chains_added = set()
        for store in chain_matches:
            chain_name = store.get('chain', '')
            if chain_name not in chains_added:
                suggestions.append({
                    'text': chain_name,
                    'type': 'chain',
                    'store_id': store.get('store_id'),
                    'store_name': store.get('store_name', ''),
                    'location': store.get('store_location', ''),
                    'display_text': f"{chain_name} - {store.get('store_name', '')}"
                })
                chains_added.add(chain_name)
    
    # Location suggestions
    if suggestion_type in ['all', 'location'] and len(suggestions) < limit:
        remaining_limit = limit - len(suggestions)
        location_matches = metadata_db.stores.find(
            {'store_location': contains_pattern},
            {'store_location': 1, 'store_name': 1, 'chain': 1, 'store_id': 1}
        ).limit(remaining_limit)
        
        for store in location_matches:
            suggestions.append({
                'text': store.get('store_location', ''),
                'type': 'location', 
                'store_id': store.get('store_id'),
                'store_name': store.get('store_name', ''),
                'chain': store.get('chain', ''),
                'display_text': f"{store.get('store_name', '')} - {store.get('store_location', '')}"
            })
    
    return {
        'suggestions': suggestions[:limit],
        'total': len(suggestions[:limit]),
        'query': query,
        'suggestion_type': suggestion_type
    }

def get_near_stores_data(user_email, refresh=False, radius_km=10, limit=20):
    """Lấy near stores từ user collection trong primary_db"""
    try:
        # Get user data
        user_data = primary_db.users.find_one({'email': user_email})
        if not user_data:
            return None, "User not found"
        
        # Check if user has location
        user_location = user_data.get('location')
        if not user_location:
            return None, "User location not set. Please update your location first."
        
        latitude = user_location.get('latitude')
        longitude = user_location.get('longitude')
        
        if not latitude or not longitude:
            return None, "Invalid user location coordinates"
        
        # Get cached near_stores or refresh if requested
        near_stores = user_data.get('near_stores', [])
        near_stores_updated_at = user_data.get('near_stores_updated_at')
        # Apply additional filtering if needed
        filtered_stores = []
        for store in near_stores:
            distance_km = store.get('distance_km', float('inf'))
            if distance_km <= radius_km:
                filtered_stores.append(store)
        
        # Sort by distance and limit results
        filtered_stores.sort(key=lambda x: x.get('distance_km', float('inf')))
        result_stores = filtered_stores[:limit]
        
        # Enhance store data with additional info
        for store in result_stores:
            if '_id' in store:
                store['_id'] = str(store['_id'])
            store['is_nearby'] = True
            store['search_radius_km'] = radius_km
            
            # Add route info summary if available
            if 'route_info' in store:
                route_info = store['route_info']
                store['route_summary'] = {
                    'distance_km': route_info.get('distance_km', store.get('distance_km', 0)),
                    'duration_minutes': route_info.get('duration_minutes', 0),
                    'estimated_time': f"{route_info.get('duration_minutes', 0):.0f} min"
                }
        
        return {
            'near_stores': result_stores,
            'total_found': len(result_stores),
            'search_params': {
                'radius_km': radius_km,
                'limit': limit
            },
            'user_location': {
                'latitude': latitude,
                'longitude': longitude,
                'address': user_location.get('address', 'Unknown')
            },
            'last_updated': near_stores_updated_at.isoformat() if near_stores_updated_at else None
        }, None
        
    except Exception as e:
        return None, str(e)