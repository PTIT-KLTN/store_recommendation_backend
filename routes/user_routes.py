from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.user_service import get_user_info_with_basket, update_user_location
from validators.user_validators import validate_location_data

user_bp = Blueprint('user', __name__)

@user_bp.route('', methods=['GET'])
@jwt_required()
def get_user_info():
    try:
        current_user_email = get_jwt_identity()
        
        user_data, error = get_user_info_with_basket(current_user_email)
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