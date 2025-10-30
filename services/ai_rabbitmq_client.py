"""
RabbitMQ RPC Client for Main Service to communicate with AI Service.
Implements recipe analysis requests via RabbitMQ message queue.
"""
import pika
import json
import uuid
import logging
import os
from typing import Dict, Any, Optional
from threading import Lock
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class AIServiceClient:
    """
    RabbitMQ RPC Client for AI Service communication.
    Implements thread-safe request-reply pattern for recipe analysis.
    """
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        username: str = None,
        password: str = None,
        virtual_host: str = '/',
        timeout: int = 30
    ):
        """
        Initialize RabbitMQ client for AI Service.
        
        Args:
            host: RabbitMQ host (defaults to RABBITMQ_HOST env var)
            port: RabbitMQ port (defaults to RABBITMQ_PORT env var)
            username: RabbitMQ username (defaults to RABBITMQ_USERNAME env var)
            password: RabbitMQ password (defaults to RABBITMQ_PASSWORD env var)
            virtual_host: RabbitMQ virtual host
            timeout: Request timeout in seconds
        """
        self.host = host or os.getenv('RABBITMQ_HOST', 'localhost')
        self.port = port or int(os.getenv('RABBITMQ_PORT', 5672))
        self.username = username or os.getenv('RABBITMQ_USERNAME', 'guest')
        self.password = password or os.getenv('RABBITMQ_PASSWORD', 'guest')
        self.virtual_host = virtual_host
        self.timeout = timeout
        self.queue_name = 'recipe_analysis_request'
        
        # Connection parameters
        credentials = pika.PlainCredentials(self.username, self.password)
        self.params = pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            virtual_host=self.virtual_host,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300
        )
        
        # Connection and channel
        self.connection = None
        self.channel = None
        self.callback_queue = None
        
        # Response handling
        self.response = None
        self.correlation_id = None
        self.lock = Lock()
        
        # Initialize connection
        self._connect()
    
    def _connect(self):
        """Establish connection to RabbitMQ."""
        try:
            self.connection = pika.BlockingConnection(self.params)
            self.channel = self.connection.channel()
            
            # Declare callback queue (exclusive, auto-delete)
            result = self.channel.queue_declare(queue='', exclusive=True)
            self.callback_queue = result.method.queue
            
            # Start consuming responses
            self.channel.basic_consume(
                queue=self.callback_queue,
                on_message_callback=self._on_response,
                auto_ack=True
            )
            
            logger.info(f"✅ Connected to RabbitMQ at {self.host}:{self.port}")
            logger.info(f"📬 Callback queue: {self.callback_queue}")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to RabbitMQ: {e}")
            raise
    
    def _on_response(self, ch, method, props, body):
        """
        Callback when response is received from AI Service.
        
        Args:
            ch: Channel
            method: Delivery method
            props: Message properties
            body: Message body
        """
        if self.correlation_id == props.correlation_id:
            try:
                self.response = json.loads(body.decode('utf-8'))
                logger.debug(f"📥 Response received for correlation_id={props.correlation_id}")
            except json.JSONDecodeError as e:
                logger.error(f"❌ Failed to decode response JSON: {e}")
                self.response = {
                    "success": False,
                    "error": f"Invalid JSON response: {str(e)}"
                }
    
    def analyze_recipe(self, user_input: str) -> Dict[str, Any]:
        """
        Send recipe analysis request to AI Service.
        
        Args:
            user_input: User's recipe request (e.g., "Tôi muốn ăn phở bò")
            
        Returns:
            Response from AI Service with recipe analysis:
            {
                "success": true/false,
                "result": {
                    "dish": {...},
                    "cart": {...},
                    "conflict_warnings": [...],
                    "suggestions": [...],
                    ...
                },
                "error": "..." (if success=false)
            }
            
        Raises:
            TimeoutError: If no response within timeout period
            Exception: For other errors
        """
        with self.lock:
            try:
                # Generate correlation ID
                self.correlation_id = str(uuid.uuid4())
                self.response = None
                
                # Prepare request
                request = {"user_input": user_input}
                
                logger.info(f"📤 Sending recipe analysis request: correlation_id={self.correlation_id}")
                logger.debug(f"Request body: {request}")
                
                # Publish request
                self.channel.basic_publish(
                    exchange='',
                    routing_key=self.queue_name,
                    properties=pika.BasicProperties(
                        reply_to=self.callback_queue,
                        correlation_id=self.correlation_id,
                        content_type='application/json',
                        delivery_mode=2  # Persistent message
                    ),
                    body=json.dumps(request, ensure_ascii=False).encode('utf-8')
                )
                
                # Wait for response
                import time
                start_time = time.time()
                while self.response is None:
                    self.connection.process_data_events(time_limit=1)
                    
                    elapsed = time.time() - start_time
                    if elapsed > self.timeout:
                        raise TimeoutError(
                            f"No response from AI Service within {self.timeout} seconds"
                        )
                
                logger.info(f"✅ Received response: correlation_id={self.correlation_id}")
                logger.debug(f"Response body: {self.response}")
                
                return self.response
                
            except TimeoutError:
                logger.error(f"⏱️ Timeout waiting for AI Service response (>{self.timeout}s)")
                raise
            except pika.exceptions.AMQPConnectionError as e:
                logger.error(f"❌ RabbitMQ connection error: {e}")
                raise Exception(f"RabbitMQ connection error: {str(e)}")
            except Exception as e:
                logger.error(f"❌ Error in analyze_recipe: {e}", exc_info=True)
                raise
    
    def reconnect(self):
        """Reconnect to RabbitMQ server."""
        try:
            logger.info("🔄 Attempting to reconnect to RabbitMQ...")
            self.close()
            self._connect()
            logger.info("✅ Reconnection successful")
        except Exception as e:
            logger.error(f"❌ Reconnection failed: {e}")
            raise
    
    def is_connected(self) -> bool:
        """Check if connected to RabbitMQ."""
        return (
            self.connection is not None and 
            self.connection.is_open and
            self.channel is not None and
            self.channel.is_open
        )
    
    def close(self):
        """Close RabbitMQ connection."""
        try:
            if self.connection and self.connection.is_open:
                self.connection.close()
                logger.info("🔌 RabbitMQ connection closed")
        except Exception as e:
            logger.error(f"⚠️ Error closing connection: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Singleton instance for reuse
_client_instance: Optional[AIServiceClient] = None
_client_lock = Lock()


def get_ai_service_client() -> AIServiceClient:
    """
    Get or create singleton AI Service client.
    Thread-safe singleton pattern.
    
    Returns:
        AIServiceClient instance
        
    Example:
        >>> client = get_ai_service_client()
        >>> response = client.analyze_recipe("Tôi muốn ăn phở bò")
        >>> if response['success']:
        ...     print(response['result']['dish']['name'])
    """
    global _client_instance
    
    if _client_instance is None:
        with _client_lock:
            if _client_instance is None:
                _client_instance = AIServiceClient(
                    host=os.getenv('RABBITMQ_AI_HOST'),
                    port=int(os.getenv('RABBITMQ_AI_PORT', 5672)),
                    username=os.getenv('RABBITMQ_AI_USERNAME'),
                    password=os.getenv('RABBITMQ_AI_PASSWORD'),
                    virtual_host=os.getenv('RABBITMQ_AI_VIRTUAL_HOST', '/'),
                    timeout=int(os.getenv('AI_SERVICE_TIMEOUT', 30))
                )
                logger.info("🚀 AI Service client initialized (singleton)")
    
    return _client_instance


def close_ai_service_client():
    """Close and reset the singleton AI Service client."""
    global _client_instance
    
    with _client_lock:
        if _client_instance is not None:
            _client_instance.close()
            _client_instance = None
            logger.info("🔌 AI Service client closed and reset")
