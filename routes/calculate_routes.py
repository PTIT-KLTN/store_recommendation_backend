from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.mongodb import MongoDBConnection
import time
import re
from services.calculate_service import CalculateService

caculate_service = CalculateService()
calculate_bp = Blueprint('calculate', __name__)

@calculate_bp.route('', methods=['GET'])
@jwt_required()
def calculate_basket():
    start_time = time.time()
    
    try:
        current_user_email = get_jwt_identity()
        if not current_user_email:
            return jsonify({'message': 'Invalid token'}), 401
            
        db = MongoDBConnection.get_primary_db()
        metadata_db = MongoDBConnection.get_metadata_db()
        
        # Get user and basket data
        user_data = db.users.find_one({'email': current_user_email})
        if not user_data:
            return jsonify({'message': 'User not found'}), 404
        
        saved_baskets = user_data.get('saved_baskets', [])
        if not saved_baskets:
            return jsonify({'message': 'Không tìm thấy giỏ hàng!', 'store_recommendations': []}), 400
        
        basket_data = saved_baskets[-1]
        if not basket_data:
            return jsonify({'message': 'Empty basket', 'store_recommendations': []}), 200
        
        # Extract ingredients list and dishes list
        ingredients_list = basket_data.get('ingredients', [])
        dishes_list = basket_data.get('dishes', [])
        
        if not ingredients_list and not dishes_list:
            return jsonify({'message': 'Basket is empty', 'store_recommendations': []}), 200
        
        processed_ingredients = caculate_service.process_all_ingredients(ingredients_list, dishes_list)

        # print(processed_ingredients)

        if not processed_ingredients:
            return jsonify({'message': 'Lỗi xử lý dữ liệu!', 'store_recommendations': []}), 400
        
        # Get cached stores
        near_stores = user_data.get('near_stores', [])
        if not near_stores:
            return jsonify({'message': 'Vui lòng cập nhật vị trí của bạn trước!', 'store_recommendations': []}), 400
        
        candidate_stores = near_stores[:8]  # Limit to top 8 for performance
        
        # Find products and calculate scores
        store_calculations = caculate_service.find_matched_products(
            metadata_db, candidate_stores, processed_ingredients
        )
        
        store_calculations = caculate_service.calculate_store_scores(store_calculations, current_user_email, db)
        store_calculations.sort(key=lambda x: x['overall_score'], reverse=True)
        
        total_time = time.time() - start_time
        
        return jsonify({
            'message': 'Success',
            'store_recommendations': store_calculations,
            'total_ingredients': len(processed_ingredients),
            'calculation_time_ms': round(total_time * 1000, 2),
            'user_location': {
                'latitude': user_data.get('location', {}).get('latitude'),
                'longitude': user_data.get('location', {}).get('longitude'),
                'address': user_data.get('location', {}).get('address', 'Unknown')
            }
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Calculation error: {str(e)}'}), 500

