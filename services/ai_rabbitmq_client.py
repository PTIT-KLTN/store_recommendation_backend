
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
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        username: str = None,
        password: str = None,
        virtual_host: str = '/',
        timeout: int = 30
    ):

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
            
            logger.info(f"Connected to RabbitMQ at {self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to RabbitMQ: {e}")
            raise
    
    def _on_response(self, ch, method, props, body):

        if self.correlation_id == props.correlation_id:
            try:
                self.response = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError as e:
                logger.error(f"❌ Failed to decode response JSON: {e}")
                self.response = {
                    "success": False,
                    "error": f"Invalid JSON response: {str(e)}"
                }
    
    def analyze_recipe(self, user_input: str) -> Dict[str, Any]:
        with self.lock:
            try:
                # Generate correlation ID
                self.correlation_id = str(uuid.uuid4())
                self.response = None
                
                # Prepare request
                request = {"user_input": user_input}
                
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
    
    def analyze_image(self, s3_url: str, description: str = "") -> Dict[str, Any]:
        with self.lock:
            try:
                # Generate correlation ID
                self.correlation_id = str(uuid.uuid4())
                self.response = None
                
                image_data = {
                    "s3_url": s3_url,
                    "description": description
                }
                request = {
                    "user_input": json.dumps(image_data, ensure_ascii=False)
                }
                
                # Use same queue name (AI Service will detect based on request fields)
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
                
                # Wait for response (image processing may take longer)
                import time
                start_time = time.time()
                while self.response is None:
                    self.connection.process_data_events(time_limit=1)
                    
                    elapsed = time.time() - start_time
                    if elapsed > self.timeout:
                        raise TimeoutError(
                            f"No response from AI Service within {self.timeout} seconds"
                        )
                
                return self.response
                
            except TimeoutError:
                logger.error(f"Timeout waiting for AI Service image response (>{self.timeout}s)")
                raise
            except pika.exceptions.AMQPConnectionError as e:
                logger.error(f"❌ RabbitMQ connection error: {e}")
                raise Exception(f"RabbitMQ connection error: {str(e)}")
            except Exception as e:
                logger.error(f"❌ Error in analyze_image: {e}", exc_info=True)
                raise
    
    def reconnect(self):
        try:
            self.close()
            self._connect()
            logger.info("Reconnection successful")
        except Exception as e:
            logger.error(f"❌ Reconnection failed: {e}")
            raise
    
    def is_connected(self) -> bool:
        return (
            self.connection is not None and 
            self.connection.is_open and
            self.channel is not None and
            self.channel.is_open
        )
    
    def close(self):
        try:
            if self.connection and self.connection.is_open:
                self.connection.close()
        except Exception as e:
            logger.error(f"⚠️ Error closing connection: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Singleton instance for reuse
_client_instance: Optional[AIServiceClient] = None
_client_lock = Lock()


def get_ai_service_client() -> AIServiceClient:

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
    
    return _client_instance


def close_ai_service_client():
    global _client_instance
    
    with _client_lock:
        if _client_instance is not None:
            _client_instance.close()
            _client_instance = None
