import pika
import json
import uuid
import threading
from config import Config

class RabbitMQService:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.response_futures = {}
        self._setup_connection()
        
    def _setup_connection(self):
        self.connection = pika.BlockingConnection(
            pika.URLParameters(Config.RABBITMQ_URL)
        )
        self.channel = self.connection.channel()
        
        # Declare queues
        self.channel.queue_declare(queue=Config.RABBITMQ_PRODUCER_QUEUE, durable=True)
        self.channel.queue_declare(queue=Config.RABBITMQ_CONSUMER_QUEUE, durable=True)
        
        # Setup consumer
        self._setup_consumer()
    
    def _setup_consumer(self):
        def callback(ch, method, properties, body):
            try:
                response = json.loads(body)
                correlation_id = response.get('correlationId')
                if correlation_id in self.response_futures:
                    future = self.response_futures.pop(correlation_id)
                    future['result'] = response
                    future['event'].set()
            except Exception as e:
                print(f"Error processing response: {e}")
        
        self.channel.basic_consume(
            queue=Config.RABBITMQ_CONSUMER_QUEUE,
            on_message_callback=callback,
            auto_ack=True
        )
        
        # Start consuming in a separate thread
        def start_consuming():
            self.channel.start_consuming()
        
        consumer_thread = threading.Thread(target=start_consuming, daemon=True)
        consumer_thread.start()
    
    def send_message(self, message, timeout=25):
        correlation_id = str(uuid.uuid4())
        message['correlationId'] = correlation_id
        
        # Create future for response
        future = {
            'result': None,
            'event': threading.Event()
        }
        self.response_futures[correlation_id] = future
        
        # Send message
        self.channel.basic_publish(
            exchange='',
            routing_key=Config.RABBITMQ_PRODUCER_QUEUE,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
            )
        )
        
        # Wait for response
        if future['event'].wait(timeout):
            return future['result']
        else:
            self.response_futures.pop(correlation_id, None)
            raise TimeoutError("Request timed out")

# Global instance
rabbitmq_service = RabbitMQService()