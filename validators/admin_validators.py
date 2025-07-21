from bson import ObjectId
from validators.auth_validators import validate_email, validate_password

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
    
    required_fields = ['dish', 'vietnamese_name']
    for field in required_fields:
        if not dish_data.get(field):
            return False, f"{field} is required"
    
    return True, "Valid"

def validate_ingredient_data(ingredient_data):
    if not ingredient_data:
        return False, "No ingredient data provided"
    
    required_fields = ['name', 'category']
    for field in required_fields:
        if not ingredient_data.get(field):
            return False, f"{field} is required"
    
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