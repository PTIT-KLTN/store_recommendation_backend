from flask import Blueprint, request, jsonify
from services.public_service import (
    get_dishes_data, get_dish_categories_data, get_dish_suggestions_data,
    get_ingredients_data, get_ingredient_categories_data, get_ingredient_suggestions_data
)
from validators.public_validators import (
    validate_pagination_params, validate_suggestion_params, validate_suggestion_type
)

public_bp = Blueprint('public', __name__)

@public_bp.route('/dishes', methods=['GET'])
def get_dishes():
    try:
        page = int(request.args.get('pageNo', 0))
        size = int(request.args.get('pageSize', 30))
        
        validate_pagination_params(page, size)
        
        pattern = request.args.get('pattern', '').strip()
        dish_name = request.args.get('dish', '').strip()
        category = request.args.get('category', '').strip()
        vietnamese_name = request.args.get('vietnamese_name', '').strip()
        
        result = get_dishes_data(page, size, pattern, dish_name, category, vietnamese_name)
        return jsonify(result), 200
        
    except ValueError as ve:
        return jsonify({'message': f'Invalid parameter value: {str(ve)}'}), 400
    except Exception as e:
        return jsonify({'message': f'Error retrieving dishes: {str(e)}'}), 500

@public_bp.route('/dishes/categories', methods=['GET'])
def get_dish_categories():
    try:
        result = get_dish_categories_data()
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'message': f'Error retrieving categories: {str(e)}'}), 500

@public_bp.route('/dishes/suggestions', methods=['GET'])
def get_dish_suggestions():
    try:
        query = request.args.get('q', '').strip()
        limit = int(request.args.get('limit', 10))
        
        is_valid, message = validate_suggestion_params(query, limit)
        if not is_valid:
            return jsonify({'suggestions': []}), 200
        
        result = get_dish_suggestions_data(query, limit)
        return jsonify(result), 200
        
    except ValueError as ve:
        return jsonify({'message': f'Invalid parameter: {str(ve)}'}), 400
    except Exception as e:
        return jsonify({'message': f'Error getting suggestions: {str(e)}'}), 500

@public_bp.route('/ingredients', methods=['GET'])
def get_ingredients():
    try:
        page = int(request.args.get('pageNo', 0))
        size = int(request.args.get('pageSize', 30))
        
        validate_pagination_params(page, size)
        
        pattern = request.args.get('pattern', '').strip()
        name = request.args.get('name', '').strip()
        name_en = request.args.get('name_en', '').strip()
        vietnamese_name = request.args.get('vietnamese_name', '').strip()
        category = request.args.get('category', '').strip()
        unit = request.args.get('unit', '').strip()
        
        result = get_ingredients_data(page, size, pattern, name, name_en, vietnamese_name, category, unit)
        return jsonify(result), 200
        
    except ValueError as ve:
        return jsonify({'message': f'Invalid parameter value: {str(ve)}'}), 400
    except Exception as e:
        return jsonify({
            'message': f'Error retrieving ingredients: {str(e)}'}), 500

@public_bp.route('/ingredients/categories', methods=['GET'])
def get_ingredient_categories():
    try:
        result = get_ingredient_categories_data()
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'message': f'Error retrieving categories: {str(e)}'}), 500

@public_bp.route('/ingredients/suggestions', methods=['GET'])
def get_ingredient_suggestions():
    try:
        query = request.args.get('q', '').strip()
        limit = int(request.args.get('limit', 10))
        suggestion_type = request.args.get('type', 'all')
        
        is_valid, message = validate_suggestion_params(query, limit)
        if not is_valid:
            return jsonify({'suggestions': []}), 200
        
        validate_suggestion_type(suggestion_type)
        
        result = get_ingredient_suggestions_data(query, limit, suggestion_type)
        return jsonify(result), 200
        
    except ValueError as ve:
        return jsonify({ 'message': f'Invalid parameter: {str(ve)}' }), 400
    except Exception as e:
        return jsonify({'message': f'Error getting suggestions: {str(e)}'}), 500