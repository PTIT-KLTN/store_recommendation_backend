from celery import Celery
from celery.schedules import crontab
from datetime import datetime
from database.mongodb import MongoDBConnection
from services.location_service import location_service
import os

# celery -A services.async_tasks worker --loglevel=info --queues=location_updates,maintenance,celery --pool=solo
# celery -A services.async_tasks beat --loglevel=info

celery_app = Celery('markendation_tasks', broker=os.getenv('REDIS_URL'), backend=os.getenv('REDIS_URL'))

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
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,

    beat_schedule={
        'cleanup-expired-tokens': {
            'task': 'services.async_tasks.async_cleanup_expired_tokens',
            # 'schedule': crontab(day_of_week=1, hour=7, minute=30) # Chạy vào thứ 2 lúc 7:30 AM
            'schedule': 60.0,  # chạy mỗi 60 giây (để test)
        },
    },
)

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def async_update_near_stores(self, user_id, location_data, force_refresh=False):
    """Async task to update near stores for a user"""
    try:
        near_stores = location_service.update_user_near_stores(
            user_id, 
            location_data, 
            force_refresh
        )
                
        print(f"CELERY DEBUG: Successfully updated near stores for user {user_id}: {len(near_stores)} stores")
        
        return {
            'user_id': user_id,
            'stores_found': len(near_stores),
            'status': 'completed',
            'updated_at': datetime.utcnow().isoformat()
        }
        
    except Exception as db_error:
        print(f"CELERY DEBUG: Failed to update error status in DB: {db_error}")
        
        # Retry logic
        if self.request.retries < self.max_retries:
            print(f"CELERY DEBUG: Retrying async_update_near_stores for user {user_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (self.request.retries + 1))
        
        return {
            'user_id': user_id,
            'status': 'failed',
            'retries': self.request.retries
        }

@celery_app.task(bind=True, max_retries=2)
def async_cleanup_expired_tokens(self):
    """Async task to cleanup expired refresh tokens"""
    try:
        db = MongoDBConnection.get_primary_db()
        
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

