from database.mongodb import MongoDBConnection
from bson import ObjectId
from datetime import datetime
from flask_bcrypt import generate_password_hash
from models.user import User
from models.basket import Basket

db = MongoDBConnection.get_primary_db()

def get_user_role(user_email):
    user_data = db.users.find_one({'email': user_email})
    if not user_data:
        return None, "User not found"
    
    return user_data.get('role', 'USER'), None

def check_super_admin_exists():
    """Check if super admin already exists"""
    super_admin = db.users.find_one({'role': 'SUPER_ADMIN'})
    return super_admin is not None

def get_user_role_and_type(user_email):
    """Get user role and check if super admin"""
    user_data = db.users.find_one({'email': user_email})
    if not user_data:
        return None, None, "User not found"
    
    role = user_data.get('role', 'USER')
    is_super_admin = role == 'SUPER_ADMIN'
    
    return role, is_super_admin, None

def create_admin_account(admin_data, is_super_admin=False):
    # Check if admin already exists
    existing_admin = db.users.find_one({'email': admin_data['email']})
    if existing_admin:
        return None, "Admin with this email already exists"
    
    # Hash password
    hashed_password = generate_password_hash(admin_data['password'])
    
    # Create admin user with appropriate role
    role = 'SUPER_ADMIN' if is_super_admin else 'ADMIN'
    user = User(
        email=admin_data['email'], 
        password=hashed_password, 
        fullname=admin_data['fullname'],
        role=role
    )
    user_dict = user.to_dict()
    
    user_result = db.users.insert_one(user_dict)
    
    # Return admin info (without password)
    admin_info = {
        'id': str(user_result.inserted_id),
        'email': admin_data['email'],
        'fullname': admin_data['fullname'],
        'role': role,
        'created_at': user_dict['created_at']
    }
    
    return admin_info, None

# Dish CRUD operations
def create_dish(dish_data):    
    result = db.dishes.insert_one(dish_data)
    dish_data['_id'] = str(result.inserted_id)
    
    return dish_data, None

def get_dish_by_id(dish_id):
    try:
        dish = db.dishes.find_one({'_id': ObjectId(dish_id)})
        if not dish:
            return None, "Dish not found"
        
        dish['_id'] = str(dish['_id'])
        return dish, None
    except Exception as e:
        return None, str(e)

def update_dish(dish_id, update_data):
    try:        
        result = db.dishes.update_one(
            {'_id': ObjectId(dish_id)},
            {'$set': update_data}
        )
        
        if result.matched_count == 0:
            return None, "Dish not found"
        
        updated_dish = db.dishes.find_one({'_id': ObjectId(dish_id)})
        updated_dish['_id'] = str(updated_dish['_id'])
        
        return updated_dish, None
    except Exception as e:
        return None, str(e)

def delete_dish(dish_id):
    try:
        result = db.dishes.delete_one({'_id': ObjectId(dish_id)})
        
        if result.deleted_count == 0:
            return None, "Dish not found"
        
        return {'message': 'Dish deleted successfully', 'dish_id': dish_id}, None
    except Exception as e:
        return None, str(e)

def get_all_dishes(page, size, search_query=None):
    skip = page * size
    
    query = {}
    if search_query:
        pattern_regex = {'$regex': search_query, '$options': 'i'}
        query = {
            '$or': [
                {'dish': pattern_regex},
                {'vietnamese_name': pattern_regex},
                {'category': pattern_regex}
            ]
        }
    
    dishes = list(
        db.dishes.find(query)
        .sort('created_at', -1)
        .skip(skip)
        .limit(size)
    )
    total = db.dishes.count_documents(query)
    
    for dish in dishes:
        dish['_id'] = str(dish['_id'])
    
    total_pages = (total + size - 1) // size if size > 0 else 0
    
    return {
        'dishes': dishes,
        'pagination': {
            'currentPage': page,
            'pageSize': size,
            'totalPages': total_pages,
            'totalElements': total,
            'hasNext': page < total_pages - 1,
            'hasPrevious': page > 0
        }
    }, None

# Ingredient CRUD operations
def create_ingredient(ingredient_data):
    result = db.ingredients.insert_one(ingredient_data)
    ingredient_data['_id'] = str(result.inserted_id)
    
    return ingredient_data, None

def get_ingredient_by_id(ingredient_id):
    try:
        ingredient = db.ingredients.find_one({'_id': ObjectId(ingredient_id)})
        if not ingredient:
            return None, "Ingredient not found"
        
        ingredient['_id'] = str(ingredient['_id'])
        return ingredient, None
    except Exception as e:
        return None, str(e)

def update_ingredient(ingredient_id, update_data):
    try:        
        result = db.ingredients.update_one(
            {'_id': ObjectId(ingredient_id)},
            {'$set': update_data}
        )
        
        if result.matched_count == 0:
            return None, "Ingredient not found"
        
        updated_ingredient = db.ingredients.find_one({'_id': ObjectId(ingredient_id)})
        updated_ingredient['_id'] = str(updated_ingredient['_id'])
        
        return updated_ingredient, None
    except Exception as e:
        return None, str(e)

def delete_ingredient(ingredient_id):
    try:
        result = db.ingredients.delete_one({'_id': ObjectId(ingredient_id)})
        
        if result.deleted_count == 0:
            return None, "Ingredient not found"
        
        return {'message': 'Ingredient deleted successfully', 'ingredient_id': ingredient_id}, None
    except Exception as e:
        return None, str(e)

def get_all_ingredients(page, size, search_query=None):
    skip = page * size
    
    query = {}
    if search_query:
        pattern_regex = {'$regex': search_query, '$options': 'i'}
        query = {
            '$or': [
                {'name': pattern_regex},
                {'name_en': pattern_regex},
                {'vietnamese_name': pattern_regex},
                {'category': pattern_regex}
            ]
        }
    
    ingredients = list(
        db.ingredients.find(query)
        .sort('created_at', -1)
        .skip(skip)
        .limit(size)
    )
    total = db.ingredients.count_documents(query)
    
    for ingredient in ingredients:
        ingredient['_id'] = str(ingredient['_id'])
    
    total_pages = (total + size - 1) // size if size > 0 else 0
    
    return {
        'ingredients': ingredients,
        'pagination': {
            'currentPage': page,
            'pageSize': size,
            'totalPages': total_pages,
            'totalElements': total,
            'hasNext': page < total_pages - 1,
            'hasPrevious': page > 0
        }
    }, None