from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.basket_service import (
    get_user_basket, save_basket_to_history, save_favorite_basket,
    get_saved_baskets, remove_saved_basket
)
from validators.basket_validators import (
    validate_basket_data, validate_basket_index, validate_favorite_basket_data
)

basket_bp = Blueprint('basket', __name__)

@basket_bp.route('', methods=['GET'])
@jwt_required()
def get_basket():
    try:
        current_user_email = get_jwt_identity()
        
        basket_data, error = get_user_basket(current_user_email)
        if error:
            return jsonify({'message': error}), 404
        
        return jsonify(basket_data), 200
        
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@basket_bp.route('/update', methods=['POST'])
@jwt_required()
def update_basket():
    try:
        current_user_email = get_jwt_identity()
        basket_data = request.get_json()
        
        is_valid, message = validate_basket_data(basket_data)
        if not is_valid:
            return jsonify({'message': message}), 400
        
        saved_basket_entry, error = save_basket_to_history(current_user_email, basket_data)
        if error:
            return jsonify({'message': error}), 404
        
        return jsonify({
            'message': 'Basket saved successfully',
            'saved_basket': saved_basket_entry
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error saving basket: {str(e)}'}), 500

@basket_bp.route('/save', methods=['POST'])
@jwt_required()
def save_favorite_basket_route():
    try:
        current_user_email = get_jwt_identity()
        basket_data = request.get_json()
        
        is_valid, message = validate_favorite_basket_data(basket_data)
        if not is_valid:
            return jsonify({'message': message}), 400
        
        basket_document, error = save_favorite_basket(current_user_email, basket_data)
        if error:
            return jsonify({'message': error}), 404
        
        return jsonify({
            'message': 'Favorite basket saved successfully',
            'basket': basket_document
        }), 201
        
    except Exception as e:
        return jsonify({'message': f'Error saving favorite basket: {str(e)}'}), 500

@basket_bp.route('/savedBaskets', methods=['GET'])
@jwt_required()
def get_saved_baskets_route():
    try:
        current_user_email = get_jwt_identity()
        
        result, error = get_saved_baskets(current_user_email)
        if error:
            return jsonify({'message': error}), 404
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'message': f'Error fetching saved baskets: {str(e)}'}), 500

@basket_bp.route('/remove/<int:basket_index>', methods=['POST'])
@jwt_required()
def remove_saved_basket_route(basket_index):
    try:
        current_user_email = get_jwt_identity()
        
        is_valid, message = validate_basket_index(basket_index)
        if not is_valid:
            return jsonify({'message': message}), 400
        
        result, error = remove_saved_basket(current_user_email, basket_index)
        if error:
            status_code = 404 if "not found" in error.lower() else 400
            return jsonify({'message': error}), status_code
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'message': f'Error removing saved basket: {str(e)}'}), 500