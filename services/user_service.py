from database.mongodb import MongoDBConnection
from bson import ObjectId
from datetime import datetime
from services.async_tasks import async_update_near_stores, location_service

db = MongoDBConnection.get_primary_db()

def get_user_info(user_email):
    """Get basic user info - only essential fields"""
    try:
        user_data = db.users.find_one({'email': user_email})
        if not user_data:
            return None, "User not found"
        
        user_info = {
            'email': user_data.get('email'),
            'fullname': user_data.get('fullname'),
            'created_at': user_data.get('created_at'),
            'location' : user_data.get('location')
        }
        
        return user_info, None
        
    except Exception as e:
        return None, f"Error getting user info: {str(e)}"

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