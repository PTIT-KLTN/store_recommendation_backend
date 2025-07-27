from database.mongodb import MongoDBConnection
from datetime import datetime
from bson import ObjectId

db = MongoDBConnection.get_primary_db()

def add_favourite_store(user_email, store_data):
    """Add store to user's favourite list"""
    try:
        user_data = db.users.find_one({'email': user_email})
        if not user_data:
            return None, "User not found"
        
        store_id = store_data.get('store_id')
        if not store_id:
            return None, "Store ID is required"
        
        # Check if store already in favourites
        favourite_stores = user_data.get('favourite_stores', [])
        if any(store.get('store_id') == store_id for store in favourite_stores):
            return None, "Store already in favourites"
        
        # Prepare store data for saving
        favourite_store = {
            'store_id': store_id,
            'store_name': store_data.get('store_name'),
            'chain': store_data.get('chain'),
            'store_location': store_data.get('store_location'),
            'phone': store_data.get('phone', ''),
            'distance_km': store_data.get('distance_km', 0),
            'totalScore': store_data.get('totalScore', 0),
            'reviewsCount': store_data.get('reviewsCount', 0),
            'added_at': datetime.utcnow()
        }
        
        # Add to user's favourite stores
        db.users.update_one(
            {'_id': user_data['_id']},
            {'$push': {'favourite_stores': favourite_store}}
        )
        
        return favourite_store, None
        
    except Exception as e:
        return None, f"Error adding favourite store: {str(e)}"

def remove_favourite_store(user_email, store_id):
    """Remove store from user's favourite list"""
    try:
        user_data = db.users.find_one({'email': user_email})
        if not user_data:
            return None, "User not found"
        
        if not store_id:
            return None, "Store ID is required"
        store_id_variants = [store_id]
        try:
            store_id_variants.append(int(store_id))
        except:
            pass
        # Remove from favourites
        result = db.users.update_one(
            {'_id': user_data['_id']},
            {'$pull': {'favourite_stores': {'store_id': {'$in': store_id_variants}}}}
        )
        
        if result.modified_count == 0:
            return None, "Store not found in favourites"
        
        return {"message": "Store removed from favourites"}, None
        
    except Exception as e:
        return None, f"Error removing favourite store: {str(e)}"

def get_favourite_stores(user_email):
    """Get user's favourite stores list"""
    try:
        user_data = db.users.find_one({'email': user_email})
        if not user_data:
            return None, "User not found"
        
        favourite_stores = user_data.get('favourite_stores', [])
        
        return {
            'favourite_stores': favourite_stores,
            'total_count': len(favourite_stores)
        }, None
        
    except Exception as e:
        return None, f"Error getting favourite stores: {str(e)}"