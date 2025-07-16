from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from flask_bcrypt import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import uuid, re
from services.google_oauth_service import google_oauth_service

from database.mongodb import MongoDBConnection
from models.user import User
from models.basket import Basket
from bson import ObjectId

auth_bp = Blueprint('auth', __name__)
db = MongoDBConnection.get_primary_db()


def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    if len(password) < 5:
        return False, "Password must be at least 5 characters long"
    return True, "Password is valid"

def create_user_tokens(user_email, auth_provider='local'):
    access_token = create_access_token(identity=user_email)
    refresh_token = create_refresh_token(identity=user_email)
    
    db.refresh_tokens.delete_many({'user_email': user_email})
    
    refresh_token_doc = {
        '_id': str(uuid.uuid4()),
        'refresh_token': refresh_token,
        'user_email': user_email,
        'expiration_time': datetime.utcnow() + timedelta(days=90),
        'created_at': datetime.utcnow(),
        'auth_provider': auth_provider
    }
    db.refresh_tokens.insert_one(refresh_token_doc)
    
    return access_token, refresh_token

def process_user(user_data, auth_provider='local'):
    try:
        email = user_data.get('email')
        fullname = user_data.get('fullname')
        password = user_data.get('password', '')
        google_id = user_data.get('google_id') or user_data.get('sub') or user_data.get('id')
        picture = user_data.get('picture', '')
        given_name = user_data.get('given_name', '')
        family_name = user_data.get('family_name', '')
        
        if not email:
            raise Exception("Email is required")
        
        if not fullname and given_name and family_name:
            fullname = f"{given_name} {family_name}".strip()
        
        if not fullname:
            raise Exception("Fullname is required")
        
        # Search for existing user
        search_query = {'email': email}
        if auth_provider == 'google' and google_id:
            search_query = {
                '$or': [
                    {'email': email},
                    {'google_id': google_id}
                ]
            }
        
        existing_user = db.users.find_one(search_query)
        
        if existing_user:
            if auth_provider == 'local':
                raise Exception("User with this email already exists")
            else:
                update_data = {'last_login': datetime.utcnow()}
                
                if google_id and not existing_user.get('google_id'):
                    update_data['google_id'] = google_id
                    update_data['auth_provider'] = 'google'
                
                if picture and not existing_user.get('picture'):
                    update_data['picture'] = picture
                
                db.users.update_one(
                    {'_id': existing_user['_id']},
                    {'$set': update_data}
                )
                
                user_email = existing_user['email']
                is_new_user = False
        else:
            if auth_provider == 'local':
                if not password:
                    raise Exception("Password is required")
                is_valid, message = validate_password(password)
                if not is_valid:
                    raise Exception(message)
                password = generate_password_hash(password)
            
            basket = Basket(user_id=None)
            basket_result = db.baskets.insert_one(basket.to_dict())
            
            user = User(email=email, password=password, fullname=fullname)
            user_dict = user.to_dict()
            user_dict.update({
                'basket_id': str(basket_result.inserted_id),
                'auth_provider': auth_provider,
                'email_verified': auth_provider == 'google',
                'last_login': datetime.utcnow()
            })
            
            if auth_provider == 'google':
                if google_id:
                    user_dict['google_id'] = google_id
                if picture:
                    user_dict['picture'] = picture
            
            user_result = db.users.insert_one(user_dict)
            
            db.baskets.update_one(
                {'_id': basket_result.inserted_id},
                {'$set': {'user_id': str(user_result.inserted_id)}}
            )
            
            user_email = email
            is_new_user = True
        
        access_token, refresh_token = create_user_tokens(user_email, auth_provider)
        
        user_data_from_db = db.users.find_one({'email': user_email})
        user_profile = {
            'id': str(user_data_from_db['_id']),
            'email': user_data_from_db['email'],
            'fullname': user_data_from_db['fullname'],
            'role': user_data_from_db.get('role', 'USER'),
            'picture': user_data_from_db.get('picture'),
            'auth_provider': user_data_from_db.get('auth_provider', auth_provider),
            'email_verified': user_data_from_db.get('email_verified', auth_provider == 'google'),
            'location': user_data_from_db.get('location'),
            'created_at': user_data_from_db.get('created_at')
        }
        
        if auth_provider == 'google':
            message = 'Google login successful'
        else:
            message = 'User registered successfully' if is_new_user else 'Login successful'
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user_profile,
            'is_new_user': is_new_user,
            'message': message
        }
        
    except Exception as e:
        raise Exception(f"Failed to process user: {str(e)}")

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register new user"""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ('email', 'password', 'fullname')):
            return jsonify({'message': 'Email, password and fullname are required'}), 400
        
        if not validate_email(data['email']):
            return jsonify({'message': 'Invalid email format'}), 400
        
        result = process_user(data, auth_provider='local')
        return jsonify(result), 201
        
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """User login"""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ('email', 'password')):
            return jsonify({'message': 'Email and password are required'}), 400
                
        user_data = db.users.find_one({'email': data['email']})
        if not user_data:
            return jsonify({'message': 'Invalid email or password'}), 401
        
        if not check_password_hash(user_data['password'], data['password']):
            return jsonify({'message': 'Invalid email or password'}), 401
        
        if not user_data.get('is_enabled', True):
            return jsonify({'message': 'Account is disabled'}), 401
        
        access_token, refresh_token = create_user_tokens(data['email'], 'local')
        
        db.users.update_one(
            {'email': data['email']},
            {'$set': {'last_login': datetime.utcnow()}}
        )
        
        user_profile = {
            'id': str(user_data['_id']),
            'email': user_data['email'],
            'fullname': user_data['fullname'],
            'role': user_data.get('role', 'USER'),
            'picture': user_data.get('picture'),
            'auth_provider': user_data.get('auth_provider', 'local'),
            'email_verified': user_data.get('email_verified', False),
            'location': user_data.get('location'),
            'created_at': user_data.get('created_at')
        }
        
        return jsonify({
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user_profile,
            'message': 'Login successful'
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Login failed: {str(e)}'}), 500

@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """Refresh access token using refresh token"""
    try:
        data = request.get_json()
        
        if not data or 'refresh_token' not in data:
            return jsonify({'message': 'Refresh token is required'}), 400
                
        refresh_token_doc = db.refresh_tokens.find_one({
            'refresh_token': data['refresh_token']
        })
        
        if not refresh_token_doc:
            return jsonify({'message': 'Invalid refresh token'}), 401
        
        if refresh_token_doc['expiration_time'] < datetime.utcnow():
            db.refresh_tokens.delete_one({'_id': refresh_token_doc['_id']})
            return jsonify({'message': 'Refresh token expired'}), 401
        
        user_email = refresh_token_doc['user_email']
        
        user_doc = db.users.find_one({'email': user_email})
        if not user_doc or not user_doc.get('is_enabled', True):
            return jsonify({'message': 'User not found or disabled'}), 401
        
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
    """User logout"""
    try:
        current_user = get_jwt_identity()        
        db.refresh_tokens.delete_many({'user_email': current_user})
        return jsonify({'message': 'Logout successful'}), 200
    except Exception as e:
        return jsonify({'message': f'Logout failed: {str(e)}'}), 500

@auth_bp.route('/google/callback-frontend', methods=['POST'])
def google_callback_frontend():
    """Handle Google OAuth callback from frontend"""
    try:
        data = request.get_json()
        
        if not data or 'code' not in data:
            return jsonify({
                'message': 'Authorization code is required',
                'error': 'MISSING_AUTH_CODE'
            }), 400
        
        authorization_code = data['code']
        
        if not google_oauth_service.client_id:
            return jsonify({
                'message': 'Google Client ID not configured',
                'error': 'MISSING_CLIENT_ID'
            }), 500
            
        if not google_oauth_service.client_secret:
            return jsonify({
                'message': 'Google Client Secret not configured', 
                'error': 'MISSING_CLIENT_SECRET'
            }), 500
        
        token_data = google_oauth_service.exchange_code_for_token(authorization_code)
        access_token = token_data.get('access_token')
        
        if not access_token:
            raise Exception("No access token received from Google")
        
        google_user_info = google_oauth_service.get_user_info(access_token)
        
        user_data = {
            'email': google_user_info.get('email'),
            'fullname': google_user_info.get('name', ''),
            'picture': google_user_info.get('picture', ''),
            'google_id': google_user_info.get('sub') or google_user_info.get('id')
        }
        
        result = process_user(user_data, auth_provider='google')
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({
            'message': f'Google callback failed: {str(e)}',
            'error': 'GOOGLE_CALLBACK_ERROR'
        }), 500
    
@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Change user password"""
    try:
        current_user_email = get_jwt_identity()
        data = request.get_json()
        
        if not data or not all(k in data for k in ('current_password', 'new_password')):
            return jsonify({'message': 'Current password and new password are required'}), 400
        
        is_valid, message = validate_password(data['new_password'])
        if not is_valid:
            return jsonify({'message': message}), 400
        
        user_doc = db.users.find_one({'email': current_user_email})
        if not user_doc:
            return jsonify({'message': 'User not found'}), 404
        
        if not user_doc.get('password'):
            return jsonify({'message': 'Cannot change password for Google account'}), 400
        
        if not check_password_hash(user_doc['password'], data['current_password']):
            return jsonify({'message': 'Current password is incorrect'}), 401
        
        new_hashed_password = generate_password_hash(data['new_password']).decode('utf-8')
        
        db.users.update_one(
            {'email': current_user_email},
            {'$set': {'password': new_hashed_password}}
        )
        
        db.refresh_tokens.delete_many({'user_email': current_user_email})
        
        return jsonify({'message': 'Password changed successfully'}), 200
        
    except Exception as e:
        return jsonify({'message': f'Failed to change password: {str(e)}'}), 500