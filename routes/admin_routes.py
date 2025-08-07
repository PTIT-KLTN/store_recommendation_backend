from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.admin_service import (
    check_super_admin_exists, create_admin_account, 
    create_dish, get_dish_by_id, update_dish, delete_dish, get_all_dishes,
    create_ingredient, get_ingredient_by_id, update_ingredient, delete_ingredient, get_all_ingredients,
    get_all_categories, toggle_admin_status, update_admin_account, get_all_admins
)
from validators.admin_validators import (
    validate_admin_data, validate_dish_data, 
    validate_ingredient_data, validate_object_id, 
    validate_ingredient_update_data, validate_dish_update_data, 
    validate_admin_update_data
)
from validators.public_validators import validate_pagination_params
from middleware.admin_middleware import admin_required, super_admin_required

admin_bp = Blueprint('admin', __name__)

# Admin Account Management
@admin_bp.route('/create-admin', methods=['POST'])
def create_admin_route():
    """Create admin account"""
    try:
        admin_data = request.get_json()
        admin_data['password'] = '123456'
        
        is_valid, message = validate_admin_data(admin_data)
        if not is_valid:
            return jsonify({'message': message}), 400
        
        # Check if this is the first admin (super admin creation)
        super_admin_exists = check_super_admin_exists()
        
        if not super_admin_exists:
            # First admin becomes super admin - no auth required
            result, error = create_admin_account(admin_data, is_super_admin=True)
            if error:
                return jsonify({'message': error}), 400
            
            return jsonify({
                'message': 'Super admin account created successfully',
                'admin': result,
                'note': 'This is the first admin account with super admin privileges'
            }), 201
        else:
            return jsonify({
                'message': 'Super admin already exists. Use the authenticated endpoint to create regular admins.',
                'endpoint': 'POST /api/v1/admin/create-admin-auth'
            }), 403
        
    except Exception as e:
        return jsonify({'message': f'Error creating admin account: {str(e)}'}), 500

@admin_bp.route('/create-admin-auth', methods=['POST'])
@jwt_required()
@super_admin_required
def create_admin_auth_route():
    """Create admin account - requires super admin authentication"""
    try:
        current_email = get_jwt_identity()
        admin_data = request.get_json()
        admin_data['password'] = '123456'
        print(admin_data)
        
        is_valid, message = validate_admin_data(admin_data)
        if not is_valid:
            return jsonify({'message': message}), 400
        
        # Create regular admin (not super admin)
        result, error = create_admin_account(admin_data, is_super_admin=False)
        if error:
            return jsonify({'message': error}), 400
        
        return jsonify({
            'message': 'Admin account created successfully',
            'admin': result,
            'created_by': current_email
        }), 201
        
    except Exception as e:
        return jsonify({'message': f'Error creating admin account: {str(e)}'}), 500

# Dish CRUD Routes
@admin_bp.route('/dishes', methods=['POST'])
@jwt_required()
@admin_required
def create_dish_route():
    try:
        dish_data = request.get_json()
        
        is_valid, message = validate_dish_data(dish_data)
        if not is_valid:
            return jsonify({'message': message}), 400
        
        result, error = create_dish(dish_data)
        if error:
            return jsonify({'message': error}), 500
        
        return jsonify(result), 201
        
    except Exception as e:
        return jsonify({'message': f'Error creating dish: {str(e)}'}), 500

@admin_bp.route('/dishes', methods=['GET'])
@jwt_required()
@admin_required
def get_dishes_route():
    try:
        page = int(request.args.get('page', 0))
        size = int(request.args.get('size', 20))
        search = request.args.get('search', '').strip()
        
        validate_pagination_params(page, size)
        
        result, error = get_all_dishes(page, size, search if search else None)
        if error:
            return jsonify({'message': error}), 500
        
        return jsonify(result), 200
        
    except ValueError as ve:
        return jsonify({'message': f'Invalid parameter: {str(ve)}'}), 400
    except Exception as e:
        return jsonify({'message': f'Error retrieving dishes: {str(e)}'}), 500

@admin_bp.route('/dishes/<dish_id>', methods=['GET'])
@jwt_required()
@admin_required
def get_dish_route(dish_id):
    try:
        is_valid, message = validate_object_id(dish_id)
        if not is_valid:
            return jsonify({'message': message}), 400
        
        result, error = get_dish_by_id(dish_id)
        if error:
            status_code = 404 if "not found" in error.lower() else 500
            return jsonify({'message': error}), status_code
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'message': f'Error retrieving dish: {str(e)}'}), 500

@admin_bp.route('/dishes/<dish_id>', methods=['PUT'])
@jwt_required()
@admin_required
def update_dish_route(dish_id):
    try:
        is_valid, message = validate_object_id(dish_id)
        if not is_valid:
            return jsonify({'message': message}), 400
        
        update_data = request.get_json()
        
        is_valid, message = validate_dish_update_data(dish_id, update_data)
        if not is_valid:
            return jsonify({'message': message}), 400
        
        result, error = update_dish(dish_id, update_data)
        if error:
            status_code = 404 if "not found" in error.lower() else 500
            return jsonify({'message': error}), status_code
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'message': f'Error updating dish: {str(e)}'}), 500

@admin_bp.route('/dishes/<dish_id>', methods=['DELETE'])
@jwt_required()
@admin_required
def delete_dish_route(dish_id):
    try:
        is_valid, message = validate_object_id(dish_id)
        if not is_valid:
            return jsonify({'message': message}), 400
        
        result, error = delete_dish(dish_id)
        if error:
            status_code = 404 if "not found" in error.lower() else 500
            return jsonify({'message': error}), status_code
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'message': f'Error deleting dish: {str(e)}'}), 500

# Ingredient CRUD Routes
@admin_bp.route('/ingredients', methods=['POST'])
@jwt_required()
@admin_required
def create_ingredient_route():
    try:
        ingredient_data = request.get_json()
        
        is_valid, message = validate_ingredient_data(ingredient_data)
        if not is_valid:
            return jsonify({'message': message}), 400
        
        result, error = create_ingredient(ingredient_data)
        if error:
            return jsonify({'message': error}), 500
        
        return jsonify(result), 201
        
    except Exception as e:
        return jsonify({'message': f'Error creating ingredient: {str(e)}'}), 500

@admin_bp.route('/ingredients', methods=['GET'])
@jwt_required()
@admin_required
def get_ingredients_route():
    try:
        page = int(request.args.get('page', 0))
        size = int(request.args.get('size', 20))
        search = request.args.get('search', '').strip()
        category = request.args.get('category', None)
        
        validate_pagination_params(page, size)
        
        result, error = get_all_ingredients(page, size, search if search else None, category if category else None)
        if error:
            return jsonify({'message': error}), 500
        
        return jsonify(result), 200
        
    except ValueError as ve:
        return jsonify({'message': f'Invalid parameter: {str(ve)}'}), 400
    except Exception as e:
        return jsonify({'message': f'Error retrieving ingredients: {str(e)}'}), 500

@admin_bp.route('/ingredients/<ingredient_id>', methods=['GET'])
@jwt_required()
@admin_required
def get_ingredient_route(ingredient_id):
    try:
        is_valid, message = validate_object_id(ingredient_id)
        if not is_valid:
            return jsonify({'message': message}), 400
        
        result, error = get_ingredient_by_id(ingredient_id)
        if error:
            status_code = 404 if "not found" in error.lower() else 500
            return jsonify({'message': error}), status_code
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'message': f'Error retrieving ingredient: {str(e)}'}), 500



@admin_bp.route('/ingredients/<ingredient_id>', methods=['PUT'])
@jwt_required()
@admin_required
def update_ingredient_route(ingredient_id):
    try:
        is_valid, message = validate_object_id(ingredient_id)
        if not is_valid:
            return jsonify({'message': message}), 400
        
        update_data = request.get_json()
        
        is_valid, message = validate_ingredient_update_data(ingredient_id, update_data)
        if not is_valid:
            return jsonify({'message': message}), 400
        
        result, error = update_ingredient(ingredient_id, update_data)
        if error:
            status_code = 404 if "not found" in error.lower() else 500
            return jsonify({'message': error}), status_code
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'message': f'Error updating ingredient: {str(e)}'}), 500

@admin_bp.route('/ingredients/<ingredient_id>', methods=['DELETE'])
@jwt_required()
@admin_required
def delete_ingredient_route(ingredient_id):
    try:
        is_valid, message = validate_object_id(ingredient_id)
        if not is_valid:
            return jsonify({'message': message}), 400
        
        result, error = delete_ingredient(ingredient_id)
        if error:
            return jsonify({'message': error}), 404 if "not found" in error.lower() else 400
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'message': f'Error deleting ingredient: {str(e)}'}), 500
    

@admin_bp.route('/categories', methods=['GET'])
@jwt_required()
@admin_required
def get_categories_route():
    """
    GET /api/v1/admin/categories
    Trả về danh sách tên các category từ metadata.categories
    """
    categories, error = get_all_categories()
    if error:
        return jsonify({'message': f'Error retrieving categories: {error}'}), 500
    return jsonify({'categories': categories}), 200


# Lấy danh sách admin thường
@admin_bp.route('/admins', methods=['GET'])
@jwt_required()
@super_admin_required
def list_admin_accounts():
    try:
        page = int(request.args.get('page', 0))
        size = int(request.args.get('size', 20))
        search = request.args.get('search', '').strip()

        result, error = get_all_admins(page, size, search if search else None)
        if error:
            return jsonify({'message': error}), 500
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'message': f'Error fetching admins: {str(e)}'}), 500


# Cập nhật email và fullname của admin
@admin_bp.route('/admins/<admin_id>', methods=['PUT'])
@jwt_required()
@super_admin_required
def update_admin_route(admin_id):
    try:
        is_valid, message = validate_object_id(admin_id)
        if not is_valid:
            return jsonify({'message': message}), 400

        update_data = request.get_json()
        is_valid, message = validate_admin_update_data(update_data)
        if not is_valid:
            return jsonify({'message': message}), 400

        result, error = update_admin_account(admin_id, update_data)
        if error:
            status_code = 404 if "not found" in error.lower() else 500
            return jsonify({'message': error}), status_code

        return jsonify({
            'message': 'Cập nhật thông tin admin thành công',
            'admin': result
        }), 200

    except Exception as e:
        return jsonify({'message': f'Error updating admin: {str(e)}'}), 500



# Bật/tắt tài khoản admin
@admin_bp.route('/admins/<admin_id>/status', methods=['PATCH'])
@jwt_required()
@super_admin_required
def update_admin_status(admin_id):
    try:
        is_valid, msg = validate_object_id(admin_id)
        if not is_valid:
            return jsonify({'message': msg}), 400

        data = request.get_json()
        if not data or 'is_enabled' not in data:
            return jsonify({'message': 'is_enabled is required'}), 400

        result, error = toggle_admin_status(admin_id, data['is_enabled'])
        if error:
            print(f"Error toggling admin status: {error}")
            return jsonify({'message': error}), 404

        return jsonify(result), 200
    except Exception as e:
        return jsonify({'message': f'Error updating admin status: {str(e)}'}), 500
    