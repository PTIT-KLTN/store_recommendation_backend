from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.store_service import (
    get_all_stores_data,
    get_store_by_id_data, 
    get_store_suggestions_data,
    get_near_stores_data
)
from validators.store_validators import (
    validate_pagination_params,
    validate_suggestion_params,
    validate_store_id
)

store_bp = Blueprint('store', __name__)

@store_bp.route('', methods=['GET'])
def get_stores():
    """API lấy danh sách các stores từ metadata_db"""
    try:
        page = int(request.args.get('pageNo', 0))
        size = int(request.args.get('pageSize', 20))
        
        validate_pagination_params(page, size)
        
        # Optional filters
        pattern = request.args.get('pattern', '').strip()
        store_name = request.args.get('store_name', '').strip() 
        chain = request.args.get('chain', '').strip()
        store_location = request.args.get('store_location', '').strip()
        
        result = get_all_stores_data(page, size, pattern, store_name, chain, store_location)
        return jsonify(result), 200
        
    except ValueError as ve:
        return jsonify({'message': f'Invalid parameter value: {str(ve)}'}), 400
    except Exception as e:
        return jsonify({'message': f'Error retrieving stores: {str(e)}'}), 500

@store_bp.route('/<store_id>', methods=['GET'])
def get_store_detail(store_id):
    """API lấy chi tiết store theo store_id"""
    try:
        is_valid, message = validate_store_id(store_id)
        if not is_valid:
            return jsonify({'message': message}), 400
            
        result, error = get_store_by_id_data(store_id)
        
        if error:
            return jsonify({'message': error}), 404
            
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'message': f'Error retrieving store details: {str(e)}'}), 500

@store_bp.route('/suggestions', methods=['GET'])
def get_store_suggestions():
    """API search suggestion cho stores"""
    try:
        query = request.args.get('q', '').strip()
        limit = int(request.args.get('limit', 10))
        suggestion_type = request.args.get('type', 'all').strip()
        
        is_valid, message = validate_suggestion_params(query, limit)
        if not is_valid:
            return jsonify({'suggestions': []}), 200
            
        result = get_store_suggestions_data(query, limit, suggestion_type)
        return jsonify(result), 200
        
    except ValueError as ve:
        return jsonify({'message': f'Invalid parameter: {str(ve)}'}), 400
    except Exception as e:
        return jsonify({'message': f'Error getting store suggestions: {str(e)}'}), 500

@store_bp.route('/near', methods=['GET'])
@jwt_required()
def get_near_stores():
    """API lấy near stores từ collection user trong primary_db"""
    try:
        current_user_email = get_jwt_identity()
        if not current_user_email:
            return jsonify({'message': 'Invalid token'}), 401
            
        # Optional parameters
        refresh = request.args.get('refresh', 'false').lower() == 'true'
        radius_km = float(request.args.get('radius_km', 10))
        limit = int(request.args.get('limit', 20))
        
        if radius_km <= 0 or radius_km > 50:
            return jsonify({'message': 'Radius must be between 1 and 50 km'}), 400
            
        if limit <= 0 or limit > 100:
            return jsonify({'message': 'Limit must be between 1 and 100'}), 400
        
        result, error = get_near_stores_data(current_user_email, refresh, radius_km, limit)
        
        if error:
            return jsonify({'message': error}), 400
            
        return jsonify(result), 200
        
    except ValueError as ve:
        return jsonify({'message': f'Invalid parameter: {str(ve)}'}), 400
    except Exception as e:
        return jsonify({'message': f'Error retrieving near stores: {str(e)}'}), 500
