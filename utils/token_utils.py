from flask_jwt_extended import create_access_token, create_refresh_token
from datetime import datetime, timedelta
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