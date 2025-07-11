import os
from datetime import timedelta

class Config:
    # MongoDB configurations
    MONGODB_PRIMARY_URI = os.getenv('MONGODB_PRIMARY_URI')
    MONGODB_METADATA_URI = os.getenv('MONGODB_METADATA_URI', 'mongodb://metadata_host:port/metadata_db')
    
    # JWT configurations
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=90)
    
    # RabbitMQ configurations
    RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@localhost:5672/')
    RABBITMQ_PRODUCER_QUEUE = os.getenv('RABBITMQ_PRODUCER_QUEUE', 'ingredient-extraction')
    RABBITMQ_CONSUMER_QUEUE = os.getenv('RABBITMQ_CONSUMER_QUEUE', 'ingredient-response')
    
    # AWS S3 configurations
    AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
    AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY')
    AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
    AWS_BUCKET_NAME = os.getenv('AWS_BUCKET_NAME')
    AWS_ENDPOINT = os.getenv('AWS_ENDPOINT')
    
    # OpenRoute API
    OPENROUTE_API_KEY = os.getenv('OPENROUTE_API_KEY')
    
    # Redis for Celery (if using async tasks)
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')