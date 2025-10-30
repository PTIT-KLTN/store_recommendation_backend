from flask_jwt_extended import create_access_token, create_refresh_token, decode_token as jwt_decode_token, verify_jwt_in_request, get_jwt_identity
from datetime import datetime, timedelta
from functools import wraps
from flask import jsonify
import uuid
from database.mongodb import MongoDBConnection

db = MongoDBConnection.get_primary_db()

def create_user_tokens(user_email, auth_provider='local'):
    access_token = create_access_token(identity=user_email)
    refresh_token = create_refresh_token(identity=user_email)
    
    db.refresh_tokens.delete_many({'user_email': user_email})
    
    refresh_token_doc = {
        '_id': str(uuid.uuid4()),
        'refresh_token': refresh_token,
        'user_email': user_email,
        'expiration_time': datetime.now() + timedelta(days=90),
        'created_at': datetime.now(),
        'auth_provider': auth_provider
    }
    db.refresh_tokens.insert_one(refresh_token_doc)
    
    return access_token, refresh_token


def decode_token(token):
    try:
        decoded = jwt_decode_token(token)
        return decoded
    except Exception:
        return None


def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            verify_jwt_in_request()
            current_user_email = get_jwt_identity()
            
            user = db.users.find_one({'email': current_user_email})
            if not user:
                return jsonify({'message': 'User not found'}), 404
            
            return f({'email': current_user_email}, *args, **kwargs)
        except Exception as e:
            return jsonify({'message': 'Invalid or expired token'}), 401
    
    return decorated_function