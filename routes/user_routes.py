from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.user_service import get_user_info, update_user_location
from validators.user_validators import validate_location_data
from services.favourite_store_service import (
    add_favourite_store, remove_favourite_store, get_favourite_stores
)

user_bp = Blueprint('user', __name__)

@user_bp.route('', methods=['GET'])
@jwt_required()
def get_user():
    """Get basic user info"""
    try:
        current_user_email = get_jwt_identity()
        
        user_data, error = get_user_info(current_user_email)
        if error:
            return jsonify({'message': error}), 404
        
        return jsonify(user_data), 200
        
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@user_bp.route('/location', methods=['POST'])
@jwt_required()
def update_location():
    try:
        current_user_email = get_jwt_identity()
        location_data = request.get_json()
        
        is_valid, message = validate_location_data(location_data)
        if not is_valid:
            return jsonify({'message': message}), 400
        
        result, error = update_user_location(current_user_email, location_data)
        if error:
            return jsonify({'message': error}), 404
        
        return jsonify(result), 202
        
    except Exception as e:
        return jsonify({'message': f'Failed to update location: {str(e)}'}), 500
    

@user_bp.route('/favourite-stores', methods=['GET'])
@jwt_required()
def get_favourite_stores_route():
    """Get user's favourite stores"""
    try:
        current_user_email = get_jwt_identity()
        
        result, error = get_favourite_stores(current_user_email)
        if error:
            return jsonify({'message': error}), 404
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'message': f'Error getting favourite stores: {str(e)}'}), 500

@user_bp.route('/favourite-stores', methods=['POST'])
@jwt_required()
def add_favourite_store_route():
    """Add store to favourites"""
    try:
        current_user_email = get_jwt_identity()
        store_data = request.get_json()
        
        if not store_data or not store_data.get('store_id'):
            return jsonify({'message': 'Store data with store_id is required'}), 400
        
        result, error = add_favourite_store(current_user_email, store_data)
        if error:
            return jsonify({'message': error}), 400
        
        return jsonify({
            'message': 'Store added to favourites',
            'store': result
        }), 201
        
    except Exception as e:
        return jsonify({'message': f'Error adding favourite store: {str(e)}'}), 500

@user_bp.route('/favourite-stores/<store_id>', methods=['DELETE'])
@jwt_required()
def remove_favourite_store_route(store_id):
    """Remove store from favourites"""
    try:
        current_user_email = get_jwt_identity()
        
        result, error = remove_favourite_store(current_user_email, store_id)
        if error:
            return jsonify({'message': error}), 404
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'message': f'Error removing favourite store: {str(e)}'}), 500
