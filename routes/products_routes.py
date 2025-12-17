from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.products_service import get_store_products_data
from datetime import datetime

products_bp = Blueprint('products', __name__)

@products_bp.route('/store/<store_id>', methods=['GET'])
@jwt_required()
def get_store_products(store_id):
    """API lấy tất cả sản phẩm của cửa hàng theo store_id"""
    try:
        current_user_email = get_jwt_identity()
        if not current_user_email:
            return jsonify({'message': 'Invalid token'}), 401
        
        # Pagination params
        page = int(request.args.get('page', 0))
        size = int(request.args.get('size', 50))
        
        # Filter params
        category = request.args.get('category', '').strip()
        search = request.args.get('search', '').strip()
        min_price = request.args.get('min_price', type=float)
        max_price = request.args.get('max_price', type=float)
        
        # Validation
        if page < 0 or size <= 0 or size > 10000:
            return jsonify({'message': 'Invalid pagination parameters'}), 400
            
        result, error = get_store_products_data(
            store_id, page, size, category, search, min_price, max_price
        )
        
        if error:
            return jsonify({'message': error}), 404 if 'not found' in error.lower() else 500
            
        return jsonify(result), 200
        
    except ValueError as ve:
        return jsonify({'message': f'Invalid parameter: {str(ve)}'}), 400
    except Exception as e:
        return jsonify({'message': f'Error retrieving products: {str(e)}'}), 500

@products_bp.route('/store/<store_id>/categories', methods=['GET'])
@jwt_required()
def get_store_categories(store_id):
    """API lấy danh sách categories có sản phẩm trong store"""
    try:
        current_user_email = get_jwt_identity()
        if not current_user_email:
            return jsonify({'message': 'Invalid token'}), 401
            
        from services.products_service import get_store_categories_data
        result, error = get_store_categories_data(store_id)
        
        if error:
            return jsonify({'message': error}), 404 if 'not found' in error.lower() else 500
            
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'message': f'Error retrieving categories: {str(e)}'}), 500

@products_bp.route('/store/<store_id>/stats', methods=['GET'])
@jwt_required()
def get_store_products_stats(store_id):
    """API lấy thống kê sản phẩm của store"""
    try:
        current_user_email = get_jwt_identity()
        if not current_user_email:
            return jsonify({'message': 'Invalid token'}), 401
            
        from services.products_service import get_store_stats_data
        result, error = get_store_stats_data(store_id)
        
        if error:
            return jsonify({'message': error}), 404 if 'not found' in error.lower() else 500
            
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'message': f'Error retrieving store stats: {str(e)}'}), 500