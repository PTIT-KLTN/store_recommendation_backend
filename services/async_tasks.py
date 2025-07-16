from celery import Celery
from datetime import datetime
from bson import ObjectId
from database.mongodb import MongoDBConnection
from services.location_service import location_service
import os
# Initialize Celery
celery_app = Celery(
    'markendation_tasks',
    broker=os.getenv('REDIS_URL'),
    backend=os.getenv('REDIS_URL')
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Ho_Chi_Minh',
    enable_utc=True,
    task_routes={
        'services.async_tasks.async_update_near_stores': {'queue': 'location_updates'},
        'services.async_tasks.async_cleanup_expired_tokens': {'queue': 'maintenance'},
    },
    # Task retry configuration
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Fix for Celery 6.0 compatibility
    broker_connection_retry_on_startup=True,
)

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def async_update_near_stores(self, user_id, location_data, force_refresh=False):
    """
    Async task to update near stores for a user
    """
    try:
        print(f"🔍 CELERY DEBUG: Starting async near stores update for user: {user_id}")
        print(f"🔍 CELERY DEBUG: Location data: {location_data}")
        
        # Update near stores using location service
        near_stores = location_service.update_user_near_stores(
            user_id, 
            location_data, 
            force_refresh
        )
        
        print(f"🔍 CELERY DEBUG: Location service returned {len(near_stores)} stores")
        
        # Update task completion status
        db = MongoDBConnection.get_primary_db()
        update_result = db.users.update_one(
            {'_id': ObjectId(user_id)},
            {
                '$set': {
                    'last_near_stores_update': datetime.utcnow(),
                    'near_stores_update_status': 'completed'
                }
            }
        )
        
        print(f"🔍 CELERY DEBUG: DB update result - matched: {update_result.matched_count}, modified: {update_result.modified_count}")
        print(f"🔍 CELERY DEBUG: Successfully updated near stores for user {user_id}: {len(near_stores)} stores")
        
        return {
            'user_id': user_id,
            'stores_found': len(near_stores),
            'status': 'completed',
            'updated_at': datetime.utcnow().isoformat()
        }
        
    except Exception as exc:
        print(f"🔍 CELERY DEBUG: Error in async_update_near_stores for user {user_id}: {exc}")
        import traceback
        print(f"🔍 CELERY DEBUG: Full traceback: {traceback.format_exc()}")
        
        # Update error status
        try:
            db = MongoDBConnection.get_primary_db()
            db.users.update_one(
                {'_id': ObjectId(user_id)},
                {
                    '$set': {
                        'near_stores_update_status': 'failed',
                        'last_update_error': str(exc),
                        'last_update_attempt': datetime.utcnow()
                    }
                }
            )
        except Exception as db_error:
            print(f"🔍 CELERY DEBUG: Failed to update error status in DB: {db_error}")
        
        # Retry logic
        if self.request.retries < self.max_retries:
            print(f"🔍 CELERY DEBUG: Retrying async_update_near_stores for user {user_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (self.request.retries + 1), exc=exc)
        
        # Max retries reached
        return {
            'user_id': user_id,
            'status': 'failed',
            'error': str(exc),
            'retries': self.request.retries
        }

@celery_app.task(bind=True, max_retries=2)
def async_cleanup_expired_tokens(self):
    """
    Async task to cleanup expired refresh tokens
    """
    try:
        db = MongoDBConnection.get_primary_db()
        
        # Delete expired refresh tokens
        result = db.refresh_tokens.delete_many({
            'expiration_time': {'$lt': datetime.utcnow()}
        })
        
        print(f"Cleaned up {result.deleted_count} expired refresh tokens")
        
        return {
            'deleted_count': result.deleted_count,
            'status': 'completed',
            'cleaned_at': datetime.utcnow().isoformat()
        }
        
    except Exception as exc:
        print(f"Error in async_cleanup_expired_tokens: {exc}")
        
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300, exc=exc)
        
        return {
            'status': 'failed',
            'error': str(exc)
        }

@celery_app.task(bind=True, max_retries=3)
def async_update_ingredient_search_index(self, ingredient_ids=None):
    """
    Async task to update search index for ingredients
    """
    try:
        db = MongoDBConnection.get_primary_db()
        
        # Build query
        query = {}
        if ingredient_ids:
            query['_id'] = {'$in': [ObjectId(id) for id in ingredient_ids]}
        
        # Update search tokens for ingredients
        ingredients = db.ingredients.find(query)
        updated_count = 0
        
        for ingredient in ingredients:
            # Generate search tokens (n-grams)
            tokens = generate_search_tokens(ingredient)
            
            db.ingredients.update_one(
                {'_id': ingredient['_id']},
                {'$set': {'token_ngrams': tokens}}
            )
            updated_count += 1
        
        print(f"Updated search index for {updated_count} ingredients")
        
        return {
            'updated_count': updated_count,
            'status': 'completed',
            'updated_at': datetime.utcnow().isoformat()
        }
        
    except Exception as exc:
        print(f"Error updating ingredient search index: {exc}")
        
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=120, exc=exc)
        
        return {
            'status': 'failed',
            'error': str(exc)
        }

def generate_search_tokens(ingredient):
    """
    Generate search tokens for ingredient
    """
    tokens = set()
    
    # Add name tokens
    if ingredient.get('name'):
        tokens.update(create_ngrams(ingredient['name']))
    
    if ingredient.get('vietnamese_name'):
        tokens.update(create_ngrams(ingredient['vietnamese_name']))
    
    if ingredient.get('name_en'):
        tokens.update(create_ngrams(ingredient['name_en']))
    
    return list(tokens)

def create_ngrams(text, n=3):
    """
    Create n-grams from text for search indexing
    """
    if not text:
        return []
    
    text = text.lower().strip()
    tokens = []
    
    # Character n-grams
    for i in range(len(text) - n + 1):
        tokens.append(text[i:i+n])
    
    # Word tokens
    words = text.split()
    for word in words:
        if len(word) >= 2:
            tokens.append(word)
    
    return tokens

# Periodic tasks configuration
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'cleanup-expired-tokens': {
        'task': 'services.async_tasks.async_cleanup_expired_tokens',
        'schedule': crontab(minute=0, hour=2),  # Run daily at 2 AM
    },
    'update-ingredient-search-index': {
        'task': 'services.async_tasks.async_update_ingredient_search_index',
        'schedule': crontab(minute=0, hour=3),  # Run daily at 3 AM
    },
}

# Task monitoring
@celery_app.task
def health_check():
    """Simple health check task"""
    return {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'worker': 'celery'
    }