from flask import jsonify
from flask_jwt_extended import get_jwt_identity
from services.admin_service import get_user_role, get_user_role_and_type
from validators.admin_validators import validate_admin_role, validate_super_admin_role

def check_admin_access():
    """Middleware to check admin access"""
    try:
        current_user_email = get_jwt_identity()
        if not current_user_email:
            return False, "Authentication required"
        
        user_role, error = get_user_role(current_user_email)
        if error:
            return False, error
        
        is_valid, message = validate_admin_role(user_role)
        if not is_valid:
            return False, message
        
        return True, None
    except Exception as e:
        return False, str(e)

def check_super_admin_access():
    """Middleware to check super admin access"""
    try:
        current_user_email = get_jwt_identity()
        if not current_user_email:
            return False, "Authentication required"
        
        user_role, is_super_admin, error = get_user_role_and_type(current_user_email)
        if error:
            return False, error
        
        is_valid, message = validate_super_admin_role(user_role)
        if not is_valid:
            return False, message
        
        return True, None
    except Exception as e:
        return False, str(e)

def admin_required(f):
    """Decorator for admin-only routes"""
    def decorated_function(*args, **kwargs):
        is_admin, message = check_admin_access()
        if not is_admin:
            return jsonify({'message': message}), 403
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def super_admin_required(f):
    """Decorator for super admin-only routes"""
    def decorated_function(*args, **kwargs):
        is_super_admin, message = check_super_admin_access()
        if not is_super_admin:
            return jsonify({'message': message}), 403
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function