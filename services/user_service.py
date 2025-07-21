from database.mongodb import MongoDBConnection
from bson import ObjectId
from datetime import datetime
from services.async_tasks import async_update_near_stores, location_service

db = MongoDBConnection.get_primary_db()

def get_user_info_with_basket(user_email):
    user_data = db.users.find_one({'email': user_email})
    if not user_data:
        return None, "User not found"
    
    # Get user's basket
    basket_data = db.baskets.find_one({'_id': ObjectId(user_data['basket_id'])})
    
    # Remove sensitive data
    user_data.pop('password', None)
    user_data['_id'] = str(user_data['_id'])
    if basket_data:
        basket_data['_id'] = str(basket_data['_id'])
        user_data['basket'] = basket_data
    
    return user_data, None

def update_user_location(user_email, location_data):
    location_obj = {
        'latitude': float(location_data['latitude']),
        'longitude': float(location_data['longitude']),
        'address': location_data.get('address', ''),
        'updated_at': datetime.now()
    }

    # Update user location and reset near_stores
    result = db.users.update_one(
        {'email': user_email},
        {
            '$set': {
                'location': location_data,
                'near_stores': []
            }
        }
    )
    
    if result.matched_count == 0:
        return None, "User not found"
    
    # Get user ID for async task
    user_data = db.users.find_one({'email': user_email})
    user_id = str(user_data['_id'])
    
    # Trigger async task to update near stores
    async_message = 'Location updated successfully. Finding nearby stores...'
    try:
        async_update_near_stores.delay(user_id, location_obj)
    except Exception as async_error:
        print(f"Failed to start async task: {async_error}")
        # Fallback to synchronous update if async fails
        try:
            location_service.update_user_near_stores(user_id, location_obj)
            async_message = 'Location and nearby stores updated successfully'
        except Exception as sync_error:
            print(f"Failed to update near stores synchronously: {sync_error}")
            async_message = 'Location updated successfully. Nearby stores will be updated shortly'
    
    return {
        'message': async_message,
        'location': location_obj,
        'user_id': user_id
    }, None