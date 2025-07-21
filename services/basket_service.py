from database.mongodb import MongoDBConnection
from bson import ObjectId
from datetime import datetime

db = MongoDBConnection.get_primary_db()

def get_user_basket(user_email):
    user_data = db.users.find_one({'email': user_email})
    if not user_data:
        return None, "User not found"
    
    basket_data = db.baskets.find_one({'_id': ObjectId(user_data['basket_id'])})
    if basket_data:
        basket_data['_id'] = str(basket_data['_id'])
    
    return basket_data, None

def save_basket_to_history(user_email, basket_data):
    user_data = db.users.find_one({'email': user_email})
    if not user_data:
        return None, "User not found"
    
    saved_basket_entry = {
        'ingredients': basket_data.get('ingredients', []),
        'dishes': basket_data.get('dishes', []),
        'ingredients_count': len(basket_data.get('ingredients', [])),
        'dishes_count': len(basket_data.get('dishes', [])),
        'saved_at': datetime.utcnow()
    }
    
    db.users.update_one(
        {'_id': user_data['_id']},
        {
            '$push': {
                'saved_baskets': {
                    '$each': [saved_basket_entry],
                    '$slice': -5  
                }
            }
        }
    )
    
    return saved_basket_entry, None

def save_favorite_basket(user_email, basket_data):
    user_data = db.users.find_one({'email': user_email})
    if not user_data:
        return None, "User not found"
    
    basket_document = {
        'user_id': str(user_data['_id']),
        'user_email': user_email,
        'basket_name': basket_data.get('basket_name'),
        'ingredients': basket_data.get('ingredients', []),
        'dishes': basket_data.get('dishes', []),
        'ingredients_count': len(basket_data.get('ingredients', [])),
        'dishes_count': len(basket_data.get('dishes', [])),
        'is_favorite': True,
        'created_at': datetime.utcnow(),
        'updated_at': datetime.utcnow()
    }
    
    result = db.baskets.insert_one(basket_document)
    basket_id = str(result.inserted_id)
    
    basket_document['_id'] = basket_id
    
    return basket_document, None

def get_saved_baskets(user_email):
    user_data = db.users.find_one({'email': user_email})
    if not user_data:
        return None, "User not found"
    
    saved_baskets = list(db.baskets.find(
        {
            'user_id': str(user_data['_id']),
            'is_favorite': True
        }
    ).sort('created_at', -1))
    
    for basket in saved_baskets:
        basket['_id'] = str(basket['_id'])
    
    return {
        'saved_baskets': saved_baskets,
        'total_count': len(saved_baskets)
    }, None

def remove_saved_basket(user_email, basket_index):
    user_data = db.users.find_one({'email': user_email})
    if not user_data:
        return None, "User not found"
    
    saved_baskets = list(db.baskets.find(
        {
            'user_id': str(user_data['_id']),
            'is_favorite': True
        }
    ).sort('created_at', -1))
    
    if basket_index < 0 or basket_index >= len(saved_baskets):
        return None, "Invalid basket index"
    
    basket_to_remove = saved_baskets[basket_index]
    
    delete_result = db.baskets.delete_one({'_id': basket_to_remove['_id']})
    
    if delete_result.deleted_count == 0:
        return None, "Basket not found or already deleted"
    
    return {
        'message': 'Saved basket removed successfully',
        'removed_basket': {
            'basket_name': basket_to_remove.get('basket_name'),
            'created_at': basket_to_remove.get('created_at')
        },
        'remaining_count': len(saved_baskets) - 1
    }, None