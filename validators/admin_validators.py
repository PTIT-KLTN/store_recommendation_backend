import re
from bson import ObjectId
from validators.auth_validators import validate_email, validate_password
from database.mongodb import MongoDBConnection

db = MongoDBConnection.get_primary_db()

def validate_admin_role(user_role):
    if user_role not in ['ADMIN', 'SUPER_ADMIN']:
        return False, "Access denied. Admin role required"
    return True, "Valid"

def validate_super_admin_role(user_role):
    if user_role != 'SUPER_ADMIN':
        return False, "Access denied. Super admin role required"
    return True, "Valid"

def validate_admin_data(admin_data):
    if not admin_data:
        return False, "No admin data provided"
    
    required_fields = ['email', 'password', 'fullname']
    for field in required_fields:
        if not admin_data.get(field):
            return False, f"{field} is required"
    
    if not validate_email(admin_data['email']):
        return False, "Invalid email format"
    
    is_valid, message = validate_password(admin_data['password'])
    if not is_valid:
        return False, message
    
    return True, "Valid"

def validate_dish_data(dish_data):
    if not dish_data:
        return False, "No dish data provided"
    
    required_fields = ['vietnamese_name', 'ingredients']
    for field in required_fields:
        if not dish_data.get(field):
            return False, f"{field} is required"
        
    name = dish_data['vietnamese_name'].strip()
    pattern = re.compile(rf'^{re.escape(name)}$', re.IGNORECASE)
    existing = db.dishes.find_one({'vietnamese_name': pattern})
    if existing:
        return False, f"Dish with name '{name}' already exists"
    
    return True, "Valid"

def validate_dish_update_data(dish_id: str, update_data: dict):
    # 1. Dùng lại validate chung
    is_valid, message = validate_update_data(update_data)
    if not is_valid:
        return False, message

    # 2. Nếu đổi tên tiếng Việt thì không được để trống và phải duy nhất
    if 'vietnamese_name' in update_data:
        name = update_data['vietnamese_name'].strip()
        if not name:
            return False, "vietnamese_name cannot be empty"

        pattern = re.compile(rf'^{re.escape(name)}$', re.IGNORECASE)
        existing = db.dishes.find_one({'vietnamese_name': pattern})
        if existing and str(existing['_id']) != dish_id:
            return False, f"Dish with name '{name}' already exists"

    # 3. Nếu có cập nhật ingredients, phải là list không rỗng và mỗi phần tử phải có id & quantity
    if 'ingredients' in update_data:
        ings = update_data['ingredients']
        if not isinstance(ings, list) or len(ings) == 0:
            return False, "Dish must have at least one ingredient"

    return True, "Valid"

def validate_ingredient_data(ingredient_data):
    if not ingredient_data:
        return False, "No ingredient data provided"
    
    required_fields = ['name', 'category', 'unit', 'net_unit_value']
    for field in required_fields:
        if not ingredient_data.get(field):
            return False, f"{field} is required"
        
    if 'net_unit_value' in ingredient_data:
        if not isinstance(ingredient_data['net_unit_value'], (int, float)):
            return False, "net_unit_value must be a number"

    name = ingredient_data['name'].strip()
    pattern = re.compile(rf'^{re.escape(name)}$', re.IGNORECASE)
    existing = db.ingredients.find_one({'name': pattern})
    if existing:
        return False, f"Ingredient with name '{name}' already exists"
    
    return True, "Valid"

def validate_object_id(id_string):
    if not id_string:
        return False, "ID is required"
    
    try:
        ObjectId(id_string)
        return True, "Valid"
    except:
        return False, "Invalid ID format"

def validate_update_data(update_data):
    if not update_data:
        return False, "No update data provided"
    
    if not isinstance(update_data, dict):
        return False, "Invalid update data format"
    
    # Remove fields that shouldn't be updated
    restricted_fields = ['_id', 'created_at']
    for field in restricted_fields:
        if field in update_data:
            del update_data[field]
    
    return True, "Valid"

def validate_ingredient_update_data(ingredient_id: str, update_data: dict):
    is_valid, message = validate_update_data(update_data)
    if not is_valid:
        return False, message

    if 'name' not in update_data:
        return True, "Valid"

    name = update_data['name'].strip()
    pattern = re.compile(rf'^{re.escape(name)}$', re.IGNORECASE)

    existing = db.ingredients.find_one({'name': pattern})
    if existing and str(existing['_id']) != ingredient_id:
        return False, f"Ingredient with name '{name}' already exists"
    
    return True, "Valid"