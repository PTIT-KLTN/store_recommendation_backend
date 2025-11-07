
import logging
import os
from typing import Dict, Any, Optional
from threading import Lock
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class AIServiceClient:
    
    def __init__(
        self,
        timeout: int = 100
    ):
        self.timeout = timeout
        self.lock = Lock()
        
        # Import here to avoid circular dependency
        from services.rabbitmq_service import get_rabbitmq_service
        self._rabbitmq_service = get_rabbitmq_service()
        
        logger.info(f"AIServiceClient initialized using unified RabbitMQ connection")
    
    def analyze_recipe(self, user_input: str) -> Dict[str, Any]:
        """Analyze recipe using AI service"""
        with self.lock:
            try:
                return self._rabbitmq_service.send_ai_request(
                    user_input=user_input,
                    timeout=self.timeout
                )
                
            except TimeoutError:
                logger.error(f"⏱️ Timeout waiting for AI Service response (>{self.timeout}s)")
                raise
            except Exception as e:
                logger.error(f"❌ Error in analyze_recipe: {e}", exc_info=True)
                raise
    
    def analyze_image(self, s3_url: str, description: str = "") -> Dict[str, Any]:
        """Analyze image using AI service"""
        with self.lock:
            try:
                return self._rabbitmq_service.send_ai_image_request(
                    s3_url=s3_url,
                    description=description,
                    timeout=self.timeout
                )
                
            except TimeoutError:
                logger.error(f"Timeout waiting for AI Service image response (>{self.timeout}s)")
                raise
            except Exception as e:
                logger.error(f"❌ Error in analyze_image: {e}", exc_info=True)
                raise
    
    def reconnect(self):
        """Reconnect to RabbitMQ (delegated to RabbitMQService)"""
        try:
            self._rabbitmq_service._setup_connection()
            logger.info("Reconnection successful")
        except Exception as e:
            logger.error(f"❌ Reconnection failed: {e}")
            raise
    
    def is_connected(self) -> bool:
        """Check if connected to RabbitMQ"""
        return (
            self._rabbitmq_service.connection is not None and 
            self._rabbitmq_service.connection.is_open and
            self._rabbitmq_service.channel is not None and
            self._rabbitmq_service.channel.is_open
        )
    
    def close(self):
        """Close connection (no-op as connection is managed by RabbitMQService)"""
        # Connection is shared and managed by RabbitMQService singleton
        # So we don't actually close it here
        pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# Singleton instance for reuse
_client_instance: Optional[AIServiceClient] = None
_client_lock = Lock()


def get_ai_service_client() -> AIServiceClient:
    """Get singleton AI service client instance (backward compatible)"""
    global _client_instance
    
    if _client_instance is None:
        with _client_lock:
            if _client_instance is None:
                _client_instance = AIServiceClient(
                    timeout=int(os.getenv('AI_SERVICE_TIMEOUT', 100))
                )
    
    return _client_instance


def close_ai_service_client():
    """Close AI service client (no-op as connection is shared)"""
    global _client_instance
    
    with _client_lock:
        if _client_instance is not None:
            _client_instance.close()
            _client_instance = None
