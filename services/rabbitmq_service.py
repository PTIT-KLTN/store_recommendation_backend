import pika
import json
import uuid
import threading
import time
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging
from collections import deque
import weakref

load_dotenv()

class RabbitMQService:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.response_futures = {}
        self._consumer_thread = None
        self._is_consuming = False
        self._lock = threading.Lock()  # Thread safety
        self._response_queue_obj = deque()  # Safe deque operations
        
        # Config - Unified RabbitMQ connection
        self.rabbitmq_url = os.getenv('RABBITMQ_URL')
        print(self.rabbitmq_url)
        
        # Crawling Service queues
        self.crawling_request_queue = os.getenv('RABBITMQ_CRAWLING_REQUEST_QUEUE')
        self.crawling_response_queue = os.getenv('RABBITMQ_CRAWLING_RESPONSE_QUEUE')
        
        # AI Service queues
        self.ai_request_queue = os.getenv('AI_QUEUE_NAME')
        self.ai_callback_queues = {}  # Store AI callback queues per correlation_id
        
        # Health check
        self._last_heartbeat = datetime.now()
        self._setup_connection()
        self._start_health_monitor()
        
    def _setup_connection(self):
        """Setup RabbitMQ connection with retry logic"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                # Close existing connection if any
                self._cleanup_connection()
                
                # Create new connection with connection parameters
                params = pika.URLParameters(self.rabbitmq_url)
                params.heartbeat = 600  # 10 minutes heartbeat
                params.connection_attempts = 3
                params.retry_delay = 2
                
                self.connection = pika.BlockingConnection(params)
                self.channel = self.connection.channel()
                
                # Set QoS to prevent overwhelming
                self.channel.basic_qos(prefetch_count=10)
                
                # Declare queues for Crawling Service
                self.channel.queue_declare(queue=self.crawling_request_queue, durable=True)
                self.channel.queue_declare(queue=self.crawling_response_queue, durable=True)
                
                # Declare queue for AI Service (request queue)
                # self.channel.queue_declare(queue=self.ai_request_queue, durable=True)
                try:
                    self.channel.queue_declare(queue=self.ai_request_queue, passive=True)
                except Exception as e:
                    arguments = {'x-message-ttl': 300000}
                    self.channel.queue_declare(
                        queue=self.ai_request_queue,
                        durable=True,
                        arguments=arguments
                    )


                # Setup consumer for Crawling response queue
                self.channel.basic_consume(
                    queue=self.crawling_response_queue,
                    on_message_callback=self._handle_crawling_response,
                    auto_ack=False  # Manual ack for reliability
                )
                
                # Start consumer thread
                self._start_consumer()
                
                # Wait for consumer to start
                time.sleep(1)
                
                print(f"✅ RabbitMQ connected:")
                print(f"   - Crawling: {self.crawling_request_queue} → {self.crawling_response_queue}")
                print(f"   - AI Service: {self.ai_request_queue}")
                self._last_heartbeat = datetime.now()
                return
                
            except Exception as e:
                print(f"❌ RabbitMQ connection attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise e
                time.sleep(retry_delay)
    
    def _start_consumer(self):
        """Start consumer thread safely"""
        with self._lock:
            if self._consumer_thread and self._consumer_thread.is_alive():
                return  # Already running
            
            self._is_consuming = True
            self._consumer_thread = threading.Thread(
                target=self._consume_messages,
                daemon=True,
                name="RabbitMQ-Consumer"
            )
            self._consumer_thread.start()
    
    def _consume_messages(self):
        """Consumer loop với exception handling"""
        while self._is_consuming:
            try:
                if self.connection and not self.connection.is_closed:
                    # Process events with timeout
                    self.connection.process_data_events(time_limit=1)
                    self._last_heartbeat = datetime.now()
                else:
                    print("⚠️ Connection lost, attempting reconnect...")
                    self._setup_connection()
                    break
                    
            except pika.exceptions.AMQPConnectionError as e:
                print(f"❌ AMQP Connection error: {e}")
                self._setup_connection()
                break
            except Exception as e:
                print(f"❌ Consumer error: {e}")
                time.sleep(5)  # Backoff
    
    def _handle_crawling_response(self, ch, method, properties, body):
        """Handle response from crawling service với improved error handling"""
        try:
            response = json.loads(body)
            action = response.get('action')
            
            if action == 'task_status_update':
                # Handle status update event
                self.handle_status_event(response)
            else:
                # Handle normal correlation_id response
                correlation_id = response.get('correlationId')
                with self._lock:  # Thread-safe access
                    if correlation_id in self.response_futures:
                        future = self.response_futures.pop(correlation_id)
                        future['result'] = response
                        future['event'].set()
            
            # Acknowledge message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in response: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            print(f"❌ Error handling response: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    
    def handle_status_event(self, event):
        """Handle task status update event"""
        try:
            from database.mongodb import MongoDBConnection
            
            db = MongoDBConnection.get_primary_db()
            task_id = event.get('task_id')
            status = event.get('status')
            
            update_data = {
                'status': status,
                'updated_at': datetime.utcnow()
            }
            
            if 'result' in event:
                update_data['result'] = event['result']
            if 'error' in event:
                update_data['error'] = event['error']
            
            result = db.crawling_tasks.update_one(
                {'task_id': task_id},
                {'$set': update_data}
            )
            
            if result.matched_count > 0:
                print(f"✅ Task {task_id} status updated to {status}")
            else:
                print(f"⚠️ Task {task_id} not found for status update")
            
        except Exception as e:
            print(f"❌ Failed to handle status event: {e}")
    
    def _cleanup_expired_futures(self):
        """Clean up expired response futures"""
        current_time = datetime.now()
        expired_keys = []
        
        with self._lock:
            for correlation_id, future in self.response_futures.items():
                # Check if future is older than 5 minutes
                if hasattr(future, 'created_at'):
                    if current_time - future['created_at'] > timedelta(minutes=5):
                        expired_keys.append(correlation_id)
            
            for key in expired_keys:
                future = self.response_futures.pop(key, None)
                if future and future['event']:
                    future['event'].set()  # Unblock waiting threads
    
    def _start_health_monitor(self):
        """Start health monitoring thread"""
        def health_monitor():
            while True:
                try:
                    time.sleep(30)  # Check every 30 seconds
                    
                    # Check connection health
                    if (datetime.now() - self._last_heartbeat).seconds > 300:  # 5 minutes
                        print("⚠️ No heartbeat detected, reconnecting...")
                        self._setup_connection()
                    
                    # Cleanup expired futures
                    self._cleanup_expired_futures()
                    
                except Exception as e:
                    print(f"❌ Health monitor error: {e}")
        
        monitor_thread = threading.Thread(target=health_monitor, daemon=True)
        monitor_thread.start()
    
    def _cleanup_connection(self):
        """Safely cleanup existing connection"""
        try:
            self._is_consuming = False
            
            if self.channel and not self.channel.is_closed:
                self.channel.stop_consuming()
                self.channel.close()
            
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                
        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")
        
        self.channel = None
        self.connection = None
    
    def _ensure_connection(self):
        """Ensure connection is healthy before operations"""
        if not self.connection or self.connection.is_closed:
            self._setup_connection()
        elif not self.channel or self.channel.is_closed:
            self._setup_connection()
    
    def is_connected(self):
        """Check if RabbitMQ connection is active"""
        return (
            self.connection is not None and
            not self.connection.is_closed and
            self.channel is not None and
            not self.channel.is_closed
        )
    
    def send_request(self, action, data=None, timeout=30):
        """Send request to crawling service với improved reliability"""
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
            'event': threading.Event(),
            'created_at': datetime.now()
        }
        
        with self._lock:
            self.response_futures[correlation_id] = future
        
        try:
            self._ensure_connection()
            
            # Send message
            self.channel.basic_publish(
                exchange='',
                routing_key=self.crawling_request_queue,
                body=json.dumps(message, ensure_ascii=False),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            
            # Wait for response
            if future['event'].wait(timeout):
                return future['result']
            else:
                with self._lock:
                    self.response_futures.pop(correlation_id, None)
                raise TimeoutError(f"Request timed out after {timeout}s")
                
        except Exception as e:
            with self._lock:
                self.response_futures.pop(correlation_id, None)
            raise e
    
    def send_async_request(self, action, data=None):
        """Send async request (fire and forget) với retry logic"""
        correlation_id = str(uuid.uuid4())
        
        message = {
            'correlationId': correlation_id,
            'timestamp': datetime.utcnow().isoformat(),
            'action': action,
            **(data or {})
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self._ensure_connection()
                
                # Send message without waiting for response
                self.channel.basic_publish(
                    exchange='',
                    routing_key=self.crawling_request_queue,
                    body=json.dumps(message, ensure_ascii=False),
                    properties=pika.BasicProperties(delivery_mode=2)
                )
                
                print(f"📤 Async request sent: {action} (ID: {correlation_id})")
                return correlation_id
                
            except Exception as e:
                print(f"❌ Send attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise e
                time.sleep(1)
    
    # ========== AI Service Methods ==========
    
    def _handle_ai_response(self, ch, method, props, body):
        """Handle response from AI service"""
        correlation_id = props.correlation_id
        
        try:
            response = json.loads(body.decode('utf-8'))
            
            with self._lock:
                if correlation_id in self.response_futures:
                    future = self.response_futures.pop(correlation_id)
                    future['result'] = response
                    future['event'].set()
            
            # Acknowledge message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in AI response: {e}")
            with self._lock:
                if correlation_id in self.response_futures:
                    future = self.response_futures.pop(correlation_id)
                    future['result'] = {
                        "success": False,
                        "error": f"Invalid JSON response: {str(e)}"
                    }
                    future['event'].set()
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            print(f"❌ Error handling AI response: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    
    def send_ai_request(self, user_input: str, timeout: int = 100):
        """Send request to AI service for recipe analysis"""
        correlation_id = str(uuid.uuid4())
        
        request = {"user_input": user_input}
        
        # Create future for response
        future = {
            'result': None,
            'event': threading.Event(),
            'created_at': datetime.now()
        }
        
        with self._lock:
            self.response_futures[correlation_id] = future
        
        try:
            self._ensure_connection()
            
            # Create exclusive callback queue for this request
            result = self.channel.queue_declare(queue='', exclusive=True)
            callback_queue = result.method.queue
            
            # Setup consumer for this callback queue
            consumer_tag = self.channel.basic_consume(
                queue=callback_queue,
                on_message_callback=self._handle_ai_response,
                auto_ack=False
            )
            
            # Store callback queue info
            with self._lock:
                self.ai_callback_queues[correlation_id] = {
                    'queue': callback_queue,
                    'consumer_tag': consumer_tag
                }
            
            # Publish request
            self.channel.basic_publish(
                exchange='',
                routing_key=self.ai_request_queue,
                properties=pika.BasicProperties(
                    reply_to=callback_queue,
                    correlation_id=correlation_id,
                    content_type='application/json',
                    delivery_mode=2  # Persistent message
                ),
                body=json.dumps(request, ensure_ascii=False).encode('utf-8')
            )
            
            # Wait for response with timeout
            start_time = time.time()
            while future['result'] is None:
                self.connection.process_data_events(time_limit=1)
                
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    # Cleanup callback queue
                    with self._lock:
                        if correlation_id in self.ai_callback_queues:
                            queue_info = self.ai_callback_queues.pop(correlation_id)
                            try:
                                self.channel.basic_cancel(queue_info['consumer_tag'])
                            except:
                                pass
                    
                    raise TimeoutError(
                        f"No response from AI Service within {timeout} seconds"
                    )
            
            # Cleanup callback queue after receiving response
            with self._lock:
                if correlation_id in self.ai_callback_queues:
                    queue_info = self.ai_callback_queues.pop(correlation_id)
                    try:
                        self.channel.basic_cancel(queue_info['consumer_tag'])
                    except:
                        pass
            
            return future['result']
            
        except TimeoutError:
            print(f"⏱️ Timeout waiting for AI Service response (>{timeout}s)")
            with self._lock:
                self.response_futures.pop(correlation_id, None)
            raise
        except Exception as e:
            print(f"❌ Error in send_ai_request: {e}")
            with self._lock:
                self.response_futures.pop(correlation_id, None)
            raise
    
    def send_ai_image_request(self, s3_url: str, description: str = "", timeout: int = 100):
        """Send image analysis request to AI service"""
        correlation_id = str(uuid.uuid4())
        
        image_data = {
            "s3_url": s3_url,
            "description": description
        }
        request = {
            "user_input": json.dumps(image_data, ensure_ascii=False)
        }
        
        # Create future for response
        future = {
            'result': None,
            'event': threading.Event(),
            'created_at': datetime.now()
        }
        
        with self._lock:
            self.response_futures[correlation_id] = future
        
        try:
            self._ensure_connection()
            
            # Create exclusive callback queue for this request
            result = self.channel.queue_declare(queue='', exclusive=True)
            callback_queue = result.method.queue
            
            # Setup consumer for this callback queue
            consumer_tag = self.channel.basic_consume(
                queue=callback_queue,
                on_message_callback=self._handle_ai_response,
                auto_ack=False
            )
            
            # Store callback queue info
            with self._lock:
                self.ai_callback_queues[correlation_id] = {
                    'queue': callback_queue,
                    'consumer_tag': consumer_tag
                }
            
            # Publish request
            self.channel.basic_publish(
                exchange='',
                routing_key=self.ai_request_queue,
                properties=pika.BasicProperties(
                    reply_to=callback_queue,
                    correlation_id=correlation_id,
                    content_type='application/json',
                    delivery_mode=2  # Persistent message
                ),
                body=json.dumps(request, ensure_ascii=False).encode('utf-8')
            )
            
            # Wait for response with timeout
            start_time = time.time()
            while future['result'] is None:
                self.connection.process_data_events(time_limit=1)
                
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    # Cleanup callback queue
                    with self._lock:
                        if correlation_id in self.ai_callback_queues:
                            queue_info = self.ai_callback_queues.pop(correlation_id)
                            try:
                                self.channel.basic_cancel(queue_info['consumer_tag'])
                            except:
                                pass
                    
                    raise TimeoutError(
                        f"No response from AI Service within {timeout} seconds"
                    )
            
            # Cleanup callback queue after receiving response
            with self._lock:
                if correlation_id in self.ai_callback_queues:
                    queue_info = self.ai_callback_queues.pop(correlation_id)
                    try:
                        self.channel.basic_cancel(queue_info['consumer_tag'])
                    except:
                        pass
            
            return future['result']
            
        except TimeoutError:
            print(f"⏱️ Timeout waiting for AI Service image response (>{timeout}s)")
            with self._lock:
                self.response_futures.pop(correlation_id, None)
            raise
        except Exception as e:
            print(f"❌ Error in send_ai_image_request: {e}")
            with self._lock:
                self.response_futures.pop(correlation_id, None)
            raise
    
    def __del__(self):
        """Cleanup on destruction"""
        self._cleanup_connection()

# Global instance với lazy loading
_rabbitmq_service = None
_service_lock = threading.Lock()

def get_rabbitmq_service():
    """Get singleton RabbitMQ service instance"""
    global _rabbitmq_service
    if _rabbitmq_service is None:
        with _service_lock:
            if _rabbitmq_service is None:
                _rabbitmq_service = RabbitMQService()
    return _rabbitmq_service

# Backward compatibility
rabbitmq_service = get_rabbitmq_service()