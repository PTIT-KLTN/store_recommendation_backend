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
import queue

load_dotenv()

class RabbitMQService:
    def __init__(self):
        self.connection = None
        self.channel = None  # channel for Crawling Service
        self.ai_channel = None  #  channel for AI Service
        self.response_futures = {}
        self._consumer_thread = None
        self._io_thread = None  # Single I/O thread
        self._is_consuming = False
        self._lock = threading.Lock()  # Thread safety
        self._response_queue_obj = deque()  # Safe deque operations
        
        # Queue for publish jobs - thread-safe communication
        self._publish_queue = queue.Queue()
        
        # Config - Unified RabbitMQ connection
        self.rabbitmq_url = os.getenv('RABBITMQ_URL')
        print(self.rabbitmq_url)
        
        # Crawling Service queues
        self.crawling_request_queue = os.getenv('RABBITMQ_CRAWLING_REQUEST_QUEUE')
        self.crawling_response_queue = os.getenv('RABBITMQ_CRAWLING_RESPONSE_QUEUE')
        
        # AI Service queues
        self.ai_request_queue = os.getenv('AI_QUEUE_NAME')
        self.ai_callback_queue = None  
        self.ai_callback_queues = {}  
        
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
                
                # Create separate channel for AI Service to avoid conflicts
                self.ai_channel = self.connection.channel()
                
                # Set QoS to prevent overwhelming
                self.channel.basic_qos(prefetch_count=10)
                
                # Declare queues for Crawling Service
                self.channel.queue_declare(queue=self.crawling_request_queue, durable=True)
                self.channel.queue_declare(queue=self.crawling_response_queue, durable=True)
                
                # Declare queue for AI Service (request queue) on AI channel
                try:
                    self.ai_channel.queue_declare(queue=self.ai_request_queue, passive=True)
                except Exception as e:
                    arguments = {'x-message-ttl': 300000}
                    self.ai_channel.queue_declare(
                        queue=self.ai_request_queue,
                        durable=True,
                        arguments=arguments
                    )
                
                # Create SINGLE exclusive callback queue for ALL AI requests (RPC pattern)
                result = self.ai_channel.queue_declare(queue='', exclusive=True)
                self.ai_callback_queue = result.method.queue
                
                # Setup consumer for the single callback queue
                self.ai_channel.basic_consume(
                    queue=self.ai_callback_queue,
                    on_message_callback=self._handle_ai_response,
                    auto_ack=False
                )
                print(f"✅ AI callback queue created: {self.ai_callback_queue}")


                # Setup consumer for Crawling response queue
                self.channel.basic_consume(
                    queue=self.crawling_response_queue,
                    on_message_callback=self._handle_crawling_response,
                    auto_ack=False  # Manual ack for reliability
                )
                
                # Start single I/O thread instead of separate consumer
                self._start_io_thread()
                
                # Wait for I/O thread to start
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
    
    def _start_io_thread(self):
        """Start single I/O thread that owns all RabbitMQ operations"""
        with self._lock:
            if self._io_thread and self._io_thread.is_alive():
                return  # Already running
            
            self._is_consuming = True
            self._io_thread = threading.Thread(
                target=self._io_loop,
                daemon=True,
                name="RabbitMQ-IO-Thread"
            )
            self._io_thread.start()
    
    def _io_loop(self):
        """Single I/O thread that handles all RabbitMQ communication"""
        while self._is_consuming:
            try:
                if not self.connection or self.connection.is_closed:
                    print("⚠️ Connection lost, attempting reconnect...")
                    time.sleep(5)
                    continue
                
                # 1. Process incoming messages (consumers)
                self.connection.process_data_events(time_limit=0.1)
                self._last_heartbeat = datetime.now()
                
                # 2. Process outgoing publish jobs from queue
                try:
                    while True:  # Process all pending jobs
                        job = self._publish_queue.get_nowait()
                        self._execute_publish_job(job)
                except queue.Empty:
                    pass  # No more jobs
                
                # Small sleep to avoid busy loop
                time.sleep(0.01)
                    
            except pika.exceptions.AMQPConnectionError as e:
                print(f"❌ AMQP Connection error: {e}")
                time.sleep(5)
            except Exception as e:
                print(f"❌ I/O loop error: {e}")
                time.sleep(1)
    
    def _execute_publish_job(self, job):
        """Execute a publish job (called only by I/O thread)"""
        try:
            job_type = job['type']
            
            if job_type == 'crawling_request':
                self.channel.basic_publish(
                    exchange='',
                    routing_key=job['routing_key'],
                    body=job['body'],
                    properties=job.get('properties', pika.BasicProperties(delivery_mode=2))
                )
                
            elif job_type == 'ai_request':
                # Use the single shared callback queue (RPC pattern)
                correlation_id = job['correlation_id']
                
                # Update properties with reply_to pointing to shared callback queue
                properties = job['properties']
                properties.reply_to = self.ai_callback_queue
                
                # Publish AI request
                self.ai_channel.basic_publish(
                    exchange='',
                    routing_key=job['routing_key'],
                    body=job['body'],
                    properties=properties
                )
                print(f"🔄 AI request published: {correlation_id} → reply_to: {self.ai_callback_queue}")
                
        except Exception as e:
            print(f"❌ Error executing publish job: {e}")
            # Set error on future if applicable
            if 'correlation_id' in job:
                correlation_id = job['correlation_id']
                with self._lock:
                    if correlation_id in self.response_futures:
                        future = self.response_futures.pop(correlation_id)
                        future['result'] = {'success': False, 'error': str(e)}
                        future['event'].set()
    
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
            
            if self.ai_channel and not self.ai_channel.is_closed:
                self.ai_channel.close()
            
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                
        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")
        
        self.channel = None
        self.ai_channel = None
        self.connection = None
    
    def _ensure_connection(self):
        """Ensure connection is healthy before operations"""
        if not self.connection or self.connection.is_closed:
            self._setup_connection()
        elif not self.channel or self.channel.is_closed:
            self._setup_connection()
        elif not self.ai_channel or self.ai_channel.is_closed:
            self._setup_connection()
    
    def is_connected(self):
        """Check if RabbitMQ connection is active"""
        return (
            self.connection is not None and
            not self.connection.is_closed and
            self.channel is not None and
            not self.channel.is_closed and
            self.ai_channel is not None and
            not self.ai_channel.is_closed
        )
    
    def send_request(self, action, data=None, timeout=30):
        """Send request to crawling service - thread-safe via publish queue"""
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
            # Submit publish job to I/O thread
            job = {
                'type': 'crawling_request',
                'routing_key': self.crawling_request_queue,
                'body': json.dumps(message, ensure_ascii=False),
                'properties': pika.BasicProperties(delivery_mode=2)
            }
            self._publish_queue.put(job)
            
            # Wait for response using Event
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
        """Send async request (fire and forget) - thread-safe via publish queue"""
        correlation_id = str(uuid.uuid4())
        
        message = {
            'correlationId': correlation_id,
            'timestamp': datetime.utcnow().isoformat(),
            'action': action,
            **(data or {})
        }
        
        try:
            # Submit publish job to I/O thread
            job = {
                'type': 'crawling_request',
                'routing_key': self.crawling_request_queue,
                'body': json.dumps(message, ensure_ascii=False),
                'properties': pika.BasicProperties(delivery_mode=2)
            }
            self._publish_queue.put(job)
            
            print(f"📤 Async request queued: {action} (ID: {correlation_id})")
            return correlation_id
            
        except Exception as e:
            print(f"❌ Failed to queue async request: {e}")
            raise e
    
    # ========== AI Service Methods ==========
    
    def _handle_ai_response(self, ch, method, props, body):
        """Handle response from AI service"""
        correlation_id = props.correlation_id
        print(f"📨 AI response received: correlation_id={correlation_id}")
        
        try:
            response = json.loads(body.decode('utf-8'))
            
            with self._lock:
                if correlation_id in self.response_futures:
                    future = self.response_futures.pop(correlation_id)
                    future['result'] = response
                    future['event'].set()
                    print(f"✅ AI response matched to future: {correlation_id}")
                else:
                    print(f"⚠️ No future found for correlation_id: {correlation_id}")
            
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
        """Send request to AI service - thread-safe via publish queue"""
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
            # Submit publish job to I/O thread (which will handle callback queue setup)
            job = {
                'type': 'ai_request',
                'correlation_id': correlation_id,
                'routing_key': self.ai_request_queue,
                'body': json.dumps(request, ensure_ascii=False).encode('utf-8'),
                'properties': pika.BasicProperties(
                    correlation_id=correlation_id,
                    content_type='application/json',
                    delivery_mode=2
                )
            }
            self._publish_queue.put(job)
            
            # Wait for response using Event
            if not future['event'].wait(timeout=timeout):
                # Timeout occurred
                with self._lock:
                    self.response_futures.pop(correlation_id, None)
                
                raise TimeoutError(
                    f"No response from AI Service within {timeout} seconds"
                )
            
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
        """Send image analysis request to AI service - thread-safe via publish queue"""
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
            # Submit publish job to I/O thread queue
            job = {
                'type': 'ai_request',
                'correlation_id': correlation_id,
                'routing_key': self.ai_request_queue,
                'body': json.dumps(request, ensure_ascii=False).encode('utf-8'),
                'properties': pika.BasicProperties(
                    correlation_id=correlation_id,
                    content_type='application/json',
                    delivery_mode=2  # Persistent message
                )
            }
            self._publish_queue.put(job)
            
            # Wait for response with Event.wait()
            if not future['event'].wait(timeout=timeout):
                # Timeout occurred
                with self._lock:
                    self.response_futures.pop(correlation_id, None)
                
                raise TimeoutError(
                    f"No response from AI Service within {timeout} seconds"
                )
            
            # Response received successfully
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