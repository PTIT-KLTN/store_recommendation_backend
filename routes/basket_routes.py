from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.mongodb import MongoDBConnection
from bson import ObjectId

basket_bp = Blueprint('basket', __name__)

@basket_bp.route('', methods=['GET'])
@jwt_required()
def get_basket():
    try:
        current_user_email = get_jwt_identity()
        db = MongoDBConnection.get_primary_db()
        
        user_data = db.users.find_one({'email': current_user_email})
        if not user_data:
            return jsonify({'message': 'User not found'}), 404
        
        basket_data = db.baskets.find_one({'_id': ObjectId(user_data['basket_id'])})
        if basket_data:
            basket_data['_id'] = str(basket_data['_id'])
        
        return jsonify(basket_data), 200
        
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@basket_bp.route('/update', methods=['POST'])
@jwt_required()
def update_basket():
    try:
        current_user_email = get_jwt_identity()
        basket_data = request.get_json()
        
        db = MongoDBConnection.get_primary_db()
        
        user_data = db.users.find_one({'email': current_user_email})
        if not user_data:
            return jsonify({'message': 'User not found'}), 404
        
        # Update basket
        db.baskets.update_one(
            {'_id': ObjectId(user_data['basket_id'])},
            {'$set': basket_data}
        )
        
        # Return updated basket
        updated_basket = db.baskets.find_one({'_id': ObjectId(user_data['basket_id'])})
        updated_basket['_id'] = str(updated_basket['_id'])
        
        return jsonify(updated_basket), 200
        
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@basket_bp.route('/calculate', methods=['GET'])
@jwt_required()
def calculate_basket():
    try:
        current_user_email = get_jwt_identity()
        db = MongoDBConnection.get_primary_db()
        
        # TODO: Implement calculation logic similar to Spring Boot version
        # This would involve:
        # 1. Getting user's basket
        # 2. Finding best products for each ingredient
        # 3. Calculating costs for each store
        # 4. Returning store recommendations
        
        return jsonify({'message': 'Calculation not implemented yet'}), 501
        
    except Exception as e:
        return jsonify({'message': str(e)}), 500