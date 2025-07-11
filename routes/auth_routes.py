from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from flask_bcrypt import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import uuid
import re

from database.mongodb import MongoDBConnection
from models.user import User
from models.basket import Basket
from bson import ObjectId

auth_bp = Blueprint('auth', __name__)

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Validate password strength"""
    if len(password) < 5:
        return False, "Password must be at least 5 characters long"
    return True, "Password is valid"

@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Đăng ký người dùng mới
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or not all(k in data for k in ('email', 'password', 'fullname')):
            return jsonify({'message': 'Email, password and fullname are required'}), 400
        
        # Validate email format
        if not validate_email(data['email']):
            return jsonify({'message': 'Invalid email format'}), 400
        
        # Validate password
        is_valid, message = validate_password(data['password'])
        if not is_valid:
            return jsonify({'message': message}), 400
        
        db = MongoDBConnection.get_primary_db()
        
        # Check if user already exists
        if db.users.find_one({'email': data['email']}):
            return jsonify({'message': 'User with this email already exists'}), 400
        
        # Hash password
        hashed_password = generate_password_hash(data['password']).decode('utf-8')
        
        # Create user
        user = User(
            email=data['email'],
            password=hashed_password,
            fullname=data['fullname']
        )
        
        # Create basket for user
        basket = Basket(user_id=None)  # Will be updated after user creation
        basket_result = db.baskets.insert_one(basket.to_dict())
        
        user.basket_id = str(basket_result.inserted_id)
        user_result = db.users.insert_one(user.to_dict())
        
        # Update basket with user_id
        db.baskets.update_one(
            {'_id': basket_result.inserted_id},
            {'$set': {'user_id': str(user_result.inserted_id)}}
        )
        
        # Generate tokens
        access_token = create_access_token(identity=data['email'])
        refresh_token = create_refresh_token(identity=data['email'])
        
        # Save refresh token
        refresh_token_doc = {
            '_id': str(uuid.uuid4()),
            'refresh_token': refresh_token,
            'user_email': data['email'],
            'expiration_time': datetime.utcnow() + timedelta(days=90),
            'created_at': datetime.utcnow()
        }
        db.refresh_tokens.insert_one(refresh_token_doc)
        
        return jsonify({
            'access_token': access_token,
            'refresh_token': refresh_token,
            'message': 'User registered successfully'
        }), 201
        
    except Exception as e:
        return jsonify({'message': f'Registration failed: {str(e)}'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Đăng nhập người dùng
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or not all(k in data for k in ('email', 'password')):
            return jsonify({'message': 'Email and password are required'}), 400
        
        db = MongoDBConnection.get_primary_db()
        
        # Find user by email
        user_data = db.users.find_one({'email': data['email']})
        if not user_data:
            return jsonify({'message': 'Invalid email or password'}), 401
        
        # Check password
        if not check_password_hash(user_data['password'], data['password']):
            return jsonify({'message': 'Invalid email or password'}), 401
        
        # Check if user is enabled
        if not user_data.get('is_enabled', True):
            return jsonify({'message': 'Account is disabled'}), 401
        
        # Generate tokens
        access_token = create_access_token(identity=data['email'])
        refresh_token = create_refresh_token(identity=data['email'])
        
        # Delete old refresh tokens
        db.refresh_tokens.delete_many({'user_email': data['email']})
        
        # Save new refresh token
        refresh_token_doc = {
            '_id': str(uuid.uuid4()),
            'refresh_token': refresh_token,
            'user_email': data['email'],
            'expiration_time': datetime.utcnow() + timedelta(days=90),
            'created_at': datetime.utcnow()
        }
        db.refresh_tokens.insert_one(refresh_token_doc)
        
        return jsonify({
            'access_token': access_token,
            'refresh_token': refresh_token,
            'message': 'Login successful'
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Login failed: {str(e)}'}), 500

@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """
    Làm mới access token bằng refresh token
    """
    try:
        data = request.get_json()
        
        if not data or 'refresh_token' not in data:
            return jsonify({'message': 'Refresh token is required'}), 400
        
        db = MongoDBConnection.get_primary_db()
        
        # Find refresh token
        refresh_token_doc = db.refresh_tokens.find_one({
            'refresh_token': data['refresh_token']
        })
        
        if not refresh_token_doc:
            return jsonify({'message': 'Invalid refresh token'}), 401
        
        # Check if token is expired
        if refresh_token_doc['expiration_time'] < datetime.utcnow():
            # Delete expired token
            db.refresh_tokens.delete_one({'_id': refresh_token_doc['_id']})
            return jsonify({'message': 'Refresh token expired'}), 401
        
        # Get user email
        user_email = refresh_token_doc['user_email']
        
        # Verify user still exists and is enabled
        user_doc = db.users.find_one({'email': user_email})
        if not user_doc or not user_doc.get('is_enabled', True):
            return jsonify({'message': 'User not found or disabled'}), 401
        
        # Generate new access token
        access_token = create_access_token(identity=user_email)
        
        return jsonify({
            'access_token': access_token,
            'refresh_token': data['refresh_token'],
            'message': 'Token refreshed successfully'
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Token refresh failed: {str(e)}'}), 500

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """
    Đăng xuất người dùng (xóa refresh token)
    """
    try:
        current_user = get_jwt_identity()
        db = MongoDBConnection.get_primary_db()
        
        # Delete all refresh tokens for this user
        db.refresh_tokens.delete_many({'user_email': current_user})
        
        return jsonify({'message': 'Logout successful'}), 200
        
    except Exception as e:
        return jsonify({'message': f'Logout failed: {str(e)}'}), 500

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """
    Lấy thông tin người dùng hiện tại
    """
    try:
        current_user_email = get_jwt_identity()
        db = MongoDBConnection.get_primary_db()
        
        # Find user
        user_doc = db.users.find_one({'email': current_user_email})
        if not user_doc:
            return jsonify({'message': 'User not found'}), 404
        
        # Remove sensitive information
        user_info = {
            'id': str(user_doc['_id']),
            'email': user_doc['email'],
            'fullname': user_doc['fullname'],
            'role': user_doc.get('role', 'USER'),
            'location': user_doc.get('location'),
            'created_at': user_doc.get('created_at')
        }
        
        return jsonify(user_info), 200
        
    except Exception as e:
        return jsonify({'message': f'Failed to get user info: {str(e)}'}), 500

@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """
    Đổi mật khẩu người dùng
    """
    try:
        current_user_email = get_jwt_identity()
        data = request.get_json()
        
        if not data or not all(k in data for k in ('current_password', 'new_password')):
            return jsonify({'message': 'Current password and new password are required'}), 400
        
        # Validate new password
        is_valid, message = validate_password(data['new_password'])
        if not is_valid:
            return jsonify({'message': message}), 400
        
        db = MongoDBConnection.get_primary_db()
        
        # Find user
        user_doc = db.users.find_one({'email': current_user_email})
        if not user_doc:
            return jsonify({'message': 'User not found'}), 404
        
        # Check current password
        if not check_password_hash(user_doc['password'], data['current_password']):
            return jsonify({'message': 'Current password is incorrect'}), 401
        
        # Hash new password
        new_hashed_password = generate_password_hash(data['new_password']).decode('utf-8')
        
        # Update password
        db.users.update_one(
            {'email': current_user_email},
            {'$set': {'password': new_hashed_password}}
        )
        
        # Invalidate all refresh tokens for security
        db.refresh_tokens.delete_many({'user_email': current_user_email})
        
        return jsonify({'message': 'Password changed successfully'}), 200
        
    except Exception as e:
        return jsonify({'message': f'Failed to change password: {str(e)}'}), 500