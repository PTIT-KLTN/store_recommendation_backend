from flask_bcrypt import generate_password_hash
from datetime import datetime
from database.mongodb import MongoDBConnection
from models.user import User
from models.basket import Basket
from validators.auth_validators import validate_password
from utils.token_utils import create_user_tokens
from models.user import UserValidationError

db = MongoDBConnection.get_primary_db()

def process_user(user_data, auth_provider='local'):
    try:
        email = user_data.get('email')
        fullname = user_data.get('fullname')
        password = user_data.get('password', '')
        google_id = user_data.get('google_id') or user_data.get('sub') or user_data.get('id')
        given_name = user_data.get('given_name', '')
        family_name = user_data.get('family_name', '')
        
        if not fullname and given_name and family_name:
            fullname = f"{given_name} {family_name}".strip()
        
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
                db.users.update_one(
                    {'_id': existing_user['_id']},
                    {'$set': {}}  
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
            
            # Only save User model fields to database
            user_result = db.users.insert_one(user_dict)
            
            db.baskets.update_one(
                {'_id': basket_result.inserted_id},
                {'$set': {'user_id': str(user_result.inserted_id)}}
            )
            
            user_email = email
            is_new_user = True
        
        access_token, refresh_token = create_user_tokens(user_email, auth_provider)
        
        user_data_from_db = db.users.find_one({'email': user_email})
        user_profile = create_user_profile(user_data_from_db, auth_provider)
        
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

def create_user_profile(user_data, auth_provider):
    return {
        'id': str(user_data['_id']),
        'email': user_data['email'],
        'fullname': user_data['fullname'],
        'role': user_data.get('role', 'USER'),
        'is_enabled': user_data.get('is_enabled', True),
        'created_at': user_data.get('created_at')
    }