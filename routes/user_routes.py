from bson import ObjectId
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.mongodb import MongoDBConnection

user_bp = Blueprint('user', __name__)

@user_bp.route('', methods=['GET'])
@jwt_required()
def get_user_info():
    try:
        current_user_email = get_jwt_identity()
        db = MongoDBConnection.get_primary_db()
        
        user_data = db.users.find_one({'email': current_user_email})
        if not user_data:
            return jsonify({'message': 'User not found'}), 404
        
        # Get user's basket
        basket_data = db.baskets.find_one({'_id': ObjectId(user_data['basket_id'])})
        
        # Remove sensitive data
        user_data.pop('password', None)
        user_data['_id'] = str(user_data['_id'])
        if basket_data:
            basket_data['_id'] = str(basket_data['_id'])
            user_data['basket'] = basket_data
        
        return jsonify(user_data), 200
        
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@user_bp.route('/location', methods=['POST'])
@jwt_required()
def update_location():
    try:
        current_user_email = get_jwt_identity()
        location_data = request.get_json()
        
        db = MongoDBConnection.get_primary_db()
        
        # Update user location and reset near_stores
        db.users.update_one(
            {'email': current_user_email},
            {
                '$set': {
                    'location': location_data,
                    'near_stores': []
                }
            }
        )
        
        # TODO: Implement async task to update near stores
        # This would be equivalent to the @Async method in Spring Boot
        
        return jsonify({'message': 'Location updated successfully'}), 202
        
    except Exception as e:
        return jsonify({'message': str(e)}), 500