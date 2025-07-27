import pika
import json
import uuid
import threading
import time
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class RabbitMQService:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.response_futures = {}
        
        # Config
        self.rabbitmq_url = os.getenv('RABBITMQ_URL')
        self.request_queue = os.getenv('RABBITMQ_CRAWLING_REQUEST_QUEUE')
        self.response_queue = os.getenv('RABBITMQ_CRAWLING_RESPONSE_QUEUE')
        
        self._setup_connection()
        
    def _setup_connection(self):
        """Setup RabbitMQ connection"""
        try:
            self.connection = pika.BlockingConnection(pika.URLParameters(self.rabbitmq_url))
            self.channel = self.connection.channel()
            
            # Declare queues
            self.channel.queue_declare(queue=self.request_queue, durable=True)
            self.channel.queue_declare(queue=self.response_queue, durable=True)
            
            # Setup consumer
            self.channel.basic_consume(
                queue=self.response_queue,
                on_message_callback=self._handle_response
            )
            
            # Start consumer thread
            consumer_thread = threading.Thread(
                target=self.channel.start_consuming, 
                daemon=True
            )
            consumer_thread.start()
            
            print(f"✅ RabbitMQ connected: {self.request_queue} → {self.response_queue}")
            
        except Exception as e:
            print(f"❌ RabbitMQ connection failed: {e}")
            raise e
    
    def _handle_response(self, ch, method, properties, body):
        """Handle response from crawling service"""
        try:
            response = json.loads(body)
            correlation_id = response.get('correlationId')
            
            if correlation_id in self.response_futures:
                future = self.response_futures.pop(correlation_id)
                future['result'] = response
                future['event'].set()
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            print(f"❌ Error handling response: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    
    def send_request(self, action, data=None, timeout=30):
        """Send request to crawling service"""
        correlation_id = str(uuid.uuid4())
        
        message = {
            'correlationId': correlation_id,
            'timestamp': datetime.utcnow().isoformat(),
            'action': action,
            **(data or {})
        }
        
        # Create future for response
        future = {
            'result': None,
            'event': threading.Event()
        }
        self.response_futures[correlation_id] = future
        
        try:
            # Send message
            self.channel.basic_publish(
                exchange='',
                routing_key=self.request_queue,
                body=json.dumps(message, ensure_ascii=False),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            
            # Wait for response
            if future['event'].wait(timeout):
                return future['result']
            else:
                self.response_futures.pop(correlation_id, None)
                raise TimeoutError(f"Request timed out after {timeout}s")
                
        except Exception as e:
            self.response_futures.pop(correlation_id, None)
            raise e

# Global instance
rabbitmq_service = RabbitMQService()