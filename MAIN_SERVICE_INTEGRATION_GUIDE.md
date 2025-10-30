# Main Service - AI Service Integration Guide

**Document Version**: 1.0  
**Last Updated**: October 30, 2025  
**Target Audience**: Main Service Backend Developers

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [RabbitMQ Setup](#rabbitmq-setup)
5. [Python Implementation](#python-implementation)
6. [Node.js Implementation](#nodejs-implementation)
7. [Request/Response Format](#requestresponse-format)
8. [Error Handling](#error-handling)
9. [Testing](#testing)
10. [Production Best Practices](#production-best-practices)
11. [Troubleshooting](#troubleshooting)

---

## Overview

Main Service giao tiếp với AI Service thông qua **RabbitMQ RPC Pattern** để xử lý recipe analysis requests. Kiến trúc này đảm bảo:

- ✅ **Asynchronous communication**: Non-blocking requests
- ✅ **Scalability**: Dễ dàng scale multiple AI Service workers
- ✅ **Reliability**: Message persistence và retry mechanisms
- ✅ **Decoupling**: Services độc lập, dễ maintain

### Key Concepts

- **RPC Pattern**: Request-Reply pattern với correlation_id để match requests/responses
- **Queue**: `recipe_analysis_request` - AI Service lắng nghe trên queue này
- **Callback Queue**: Exclusive queue cho mỗi client để nhận responses
- **Correlation ID**: UUID để match request với response tương ứng

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         System Architecture                         │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────┐                                  ┌───────────────┐
│   Main Service   │                                  │  AI Service   │
│   (RPC Client)   │                                  │ (RPC Server)  │
└────────┬─────────┘                                  └───────▲───────┘
         │                                                    │
         │ 1. Publish Request                                │
         │    - Queue: recipe_analysis_request               │
         │    - Properties:                                  │
         │      • correlation_id: "uuid-123"                 │
         │      • reply_to: "amq.gen.callback_xyz"          │
         │    - Body: {"user_input": "..."}                  │
         ├───────────────────────────────────────────────────┤
         │                                                    │
         │                  RabbitMQ Broker                  │
         │         ┌────────────────────────────┐            │
         │         │  recipe_analysis_request   │            │
         │         │         (Queue)             │            │
         │         └────────────────────────────┘            │
         │                      │                             │
         │                      ├────────────────────────────►│
         │                      │ 2. Consume & Process        │
         │                      │    (ShoppingCartPipeline)   │
         │                      │                             │
         │         ┌────────────────────────────┐            │
         │         │   amq.gen.callback_xyz     │            │
         │         │    (Callback Queue)         │            │
         │         └────────────────────────────┘            │
         │◄────────┤                             │            │
         │ 3. Response                          └────────────┤
         │    - Queue: amq.gen.callback_xyz                  │
         │    - Properties:                                  │
         │      • correlation_id: "uuid-123" (same)         │
         │    - Body: {"success": true, "result": {...}}    │
         │                                                    │
         └────────────────────────────────────────────────────┘
```

### Flow Sequence

1. **Main Service** tạo exclusive callback queue
2. **Main Service** publish request lên `recipe_analysis_request` với `correlation_id` và `reply_to`
3. **AI Service** consume message từ `recipe_analysis_request`
4. **AI Service** xử lý request qua `ShoppingCartPipeline`
5. **AI Service** publish response lên `reply_to` queue với cùng `correlation_id`
6. **Main Service** consume response từ callback queue, match bằng `correlation_id`

---

## Prerequisites

### For Python Backend

```bash
pip install pika>=1.3.0
```

### For Node.js Backend

```bash
npm install amqplib
# hoặc
yarn add amqplib
```

### RabbitMQ Server

**Option 1: Docker (Recommended)**
```bash
docker run -d --name rabbitmq \
  -p 5672:5672 \
  -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=admin \
  -e RABBITMQ_DEFAULT_PASS=admin123 \
  rabbitmq:3-management
```

**Option 2: Local Installation**
- Windows: `choco install rabbitmq`
- MacOS: `brew install rabbitmq`
- Linux: `apt-get install rabbitmq-server`

---

## RabbitMQ Setup

### 1. Connection Configuration

**.env file**:
```bash
# RabbitMQ Configuration
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USERNAME=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_VIRTUAL_HOST=/

# AI Service Queue
AI_SERVICE_QUEUE=recipe_analysis_request

# Timeout Settings
AI_SERVICE_TIMEOUT=30000  # 30 seconds in milliseconds
```

### 2. Verify RabbitMQ Connection

Access RabbitMQ Management UI:
- URL: http://localhost:15672
- Default credentials: `guest` / `guest` (or your custom credentials)

Check:
- ✅ Connection is active
- ✅ Queue `recipe_analysis_request` exists (tạo tự động bởi AI Service)
- ✅ AI Service worker đang consume

---

## Python Implementation

### 1. Create RabbitMQ Client Class

**File: `services/rabbitmq_client.py`**

```python
"""
RabbitMQ RPC Client for Main Service to communicate with AI Service.
"""
import pika
import json
import uuid
import logging
from typing import Dict, Any, Optional
from threading import Lock

logger = logging.getLogger(__name__)


class AIServiceClient:
    """
    RabbitMQ RPC Client for AI Service communication.
    Implements thread-safe request-reply pattern.
    """
    
    def __init__(
        self,
        host: str = 'localhost',
        port: int = 5672,
        username: str = 'guest',
        password: str = 'guest',
        virtual_host: str = '/',
        timeout: int = 30
    ):
        """
        Initialize RabbitMQ client for AI Service.
        
        Args:
            host: RabbitMQ host
            port: RabbitMQ port
            username: RabbitMQ username
            password: RabbitMQ password
            virtual_host: RabbitMQ virtual host
            timeout: Request timeout in seconds
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.queue_name = 'recipe_analysis_request'
        
        # Connection parameters
        credentials = pika.PlainCredentials(username, password)
        self.params = pika.ConnectionParameters(
            host=host,
            port=port,
            virtual_host=virtual_host,
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
            
            logger.info(f"Connected to RabbitMQ at {self.host}:{self.port}")
            logger.info(f"Callback queue: {self.callback_queue}")
            
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
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
            self.response = json.loads(body.decode('utf-8'))
    
    def analyze_recipe(self, user_input: str) -> Dict[str, Any]:
        """
        Send recipe analysis request to AI Service.
        
        Args:
            user_input: User's recipe request
            
        Returns:
            Response from AI Service with recipe analysis
            
        Raises:
            TimeoutError: If no response within timeout
            Exception: For other errors
        """
        with self.lock:
            try:
                # Generate correlation ID
                self.correlation_id = str(uuid.uuid4())
                self.response = None
                
                # Prepare request
                request = {"user_input": user_input}
                
                logger.info(f"Sending recipe analysis request: correlation_id={self.correlation_id}")
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
                    
                    if time.time() - start_time > self.timeout:
                        raise TimeoutError(
                            f"No response from AI Service within {self.timeout} seconds"
                        )
                
                logger.info(f"Received response: correlation_id={self.correlation_id}")
                logger.debug(f"Response body: {self.response}")
                
                return self.response
                
            except TimeoutError:
                logger.error(f"Timeout waiting for AI Service response")
                raise
            except Exception as e:
                logger.error(f"Error in analyze_recipe: {e}", exc_info=True)
                raise
    
    def close(self):
        """Close RabbitMQ connection."""
        try:
            if self.connection and self.connection.is_open:
                self.connection.close()
                logger.info("RabbitMQ connection closed")
        except Exception as e:
            logger.error(f"Error closing connection: {e}")
    
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
    """
    global _client_instance
    
    if _client_instance is None:
        with _client_lock:
            if _client_instance is None:
                import os
                _client_instance = AIServiceClient(
                    host=os.getenv('RABBITMQ_HOST', 'localhost'),
                    port=int(os.getenv('RABBITMQ_PORT', 5672)),
                    username=os.getenv('RABBITMQ_USERNAME', 'guest'),
                    password=os.getenv('RABBITMQ_PASSWORD', 'guest'),
                    virtual_host=os.getenv('RABBITMQ_VIRTUAL_HOST', '/'),
                    timeout=int(os.getenv('AI_SERVICE_TIMEOUT', 30))
                )
    
    return _client_instance
```

### 2. Usage in Main Service

**Example: FastAPI Endpoint**

```python
from fastapi import APIRouter, HTTPException
from services.rabbitmq_client import get_ai_service_client
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/v1/recipe-analysis")
async def analyze_recipe(request: dict):
    """
    Analyze recipe using AI Service via RabbitMQ.
    
    Request body:
        {
            "user_input": "Tôi muốn ăn phở bò"
        }
    
    Response:
        {
            "success": true,
            "result": {
                "dish": {...},
                "cart": {...},
                "conflict_warnings": [...],
                ...
            }
        }
    """
    user_input = request.get('user_input')
    
    if not user_input:
        raise HTTPException(status_code=400, detail="user_input is required")
    
    try:
        # Get AI Service client
        client = get_ai_service_client()
        
        # Send request to AI Service
        response = client.analyze_recipe(user_input)
        
        # Check if AI Service returned success
        if not response.get('success'):
            logger.error(f"AI Service error: {response.get('error')}")
            raise HTTPException(
                status_code=500,
                detail=f"AI Service error: {response.get('error')}"
            )
        
        return response
        
    except TimeoutError as e:
        logger.error(f"AI Service timeout: {e}")
        raise HTTPException(
            status_code=504,
            detail="AI Service request timeout"
        )
    
    except Exception as e:
        logger.error(f"Error calling AI Service: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
```

**Example: Direct Usage**

```python
from services.rabbitmq_client import AIServiceClient

# Create client
client = AIServiceClient(
    host='localhost',
    port=5672,
    username='guest',
    password='guest'
)

# Send request
response = client.analyze_recipe("Tôi muốn ăn phở bò")

# Process response
if response['success']:
    result = response['result']
    print(f"Dish: {result['dish']['name']}")
    print(f"Cart items: {result['cart']['total_items']}")
    
    # Check conflicts
    conflicts = result.get('conflict_warnings', [])
    if conflicts:
        print(f"Found {len(conflicts)} conflicts:")
        for conflict in conflicts:
            print(f"  - {conflict['conflicting_item_1']} vs {conflict['conflicting_item_2']}")
            print(f"    Message: {conflict['message']}")
else:
    print(f"Error: {response['error']}")

# Close connection
client.close()
```

---

## Node.js Implementation

### 1. Create RabbitMQ Client Class

**File: `services/rabbitmq-client.js`**

```javascript
/**
 * RabbitMQ RPC Client for Main Service to communicate with AI Service.
 */
const amqp = require('amqplib');
const { v4: uuidv4 } = require('uuid');

class AIServiceClient {
  /**
   * Initialize RabbitMQ client for AI Service.
   */
  constructor(options = {}) {
    this.host = options.host || process.env.RABBITMQ_HOST || 'localhost';
    this.port = options.port || process.env.RABBITMQ_PORT || 5672;
    this.username = options.username || process.env.RABBITMQ_USERNAME || 'guest';
    this.password = options.password || process.env.RABBITMQ_PASSWORD || 'guest';
    this.virtualHost = options.virtualHost || process.env.RABBITMQ_VIRTUAL_HOST || '/';
    this.timeout = options.timeout || parseInt(process.env.AI_SERVICE_TIMEOUT) || 30000;
    
    this.queueName = 'recipe_analysis_request';
    this.connection = null;
    this.channel = null;
    this.callbackQueue = null;
    this.responseHandlers = new Map();
  }

  /**
   * Connect to RabbitMQ server.
   */
  async connect() {
    try {
      const url = `amqp://${this.username}:${this.password}@${this.host}:${this.port}/${this.virtualHost}`;
      
      this.connection = await amqp.connect(url, {
        heartbeat: 60
      });
      
      this.channel = await this.connection.createChannel();
      
      // Declare callback queue (exclusive, auto-delete)
      const q = await this.channel.assertQueue('', {
        exclusive: true,
        autoDelete: true
      });
      
      this.callbackQueue = q.queue;
      
      // Start consuming responses
      await this.channel.consume(
        this.callbackQueue,
        (msg) => this._handleResponse(msg),
        { noAck: true }
      );
      
      console.log(`Connected to RabbitMQ at ${this.host}:${this.port}`);
      console.log(`Callback queue: ${this.callbackQueue}`);
      
    } catch (error) {
      console.error('Failed to connect to RabbitMQ:', error);
      throw error;
    }
  }

  /**
   * Handle response from AI Service.
   */
  _handleResponse(msg) {
    if (!msg) return;
    
    const correlationId = msg.properties.correlationId;
    const handler = this.responseHandlers.get(correlationId);
    
    if (handler) {
      const response = JSON.parse(msg.content.toString());
      handler.resolve(response);
      this.responseHandlers.delete(correlationId);
    }
  }

  /**
   * Send recipe analysis request to AI Service.
   * 
   * @param {string} userInput - User's recipe request
   * @returns {Promise<Object>} Response from AI Service
   */
  async analyzeRecipe(userInput) {
    if (!this.channel) {
      throw new Error('Not connected to RabbitMQ. Call connect() first.');
    }

    const correlationId = uuidv4();
    const request = { user_input: userInput };
    
    console.log(`Sending recipe analysis request: correlation_id=${correlationId}`);
    console.log(`Request body:`, request);
    
    return new Promise((resolve, reject) => {
      // Set timeout
      const timeoutId = setTimeout(() => {
        this.responseHandlers.delete(correlationId);
        reject(new Error(`No response from AI Service within ${this.timeout}ms`));
      }, this.timeout);
      
      // Register response handler
      this.responseHandlers.set(correlationId, {
        resolve: (response) => {
          clearTimeout(timeoutId);
          console.log(`Received response: correlation_id=${correlationId}`);
          console.log(`Response body:`, response);
          resolve(response);
        }
      });
      
      // Send request
      this.channel.sendToQueue(
        this.queueName,
        Buffer.from(JSON.stringify(request)),
        {
          correlationId: correlationId,
          replyTo: this.callbackQueue,
          contentType: 'application/json',
          persistent: true
        }
      );
    });
  }

  /**
   * Close RabbitMQ connection.
   */
  async close() {
    try {
      if (this.channel) {
        await this.channel.close();
      }
      if (this.connection) {
        await this.connection.close();
      }
      console.log('RabbitMQ connection closed');
    } catch (error) {
      console.error('Error closing connection:', error);
    }
  }
}

// Singleton instance
let clientInstance = null;

/**
 * Get or create singleton AI Service client.
 * @returns {AIServiceClient}
 */
function getAIServiceClient() {
  if (!clientInstance) {
    clientInstance = new AIServiceClient();
  }
  return clientInstance;
}

module.exports = {
  AIServiceClient,
  getAIServiceClient
};
```

### 2. Usage in Main Service (Node.js)

**Example: Express.js Endpoint**

```javascript
const express = require('express');
const { getAIServiceClient } = require('./services/rabbitmq-client');

const router = express.Router();

// Initialize client on startup
let aiClient;
(async () => {
  aiClient = getAIServiceClient();
  await aiClient.connect();
  console.log('AI Service client ready');
})();

/**
 * POST /api/v1/recipe-analysis
 * Analyze recipe using AI Service via RabbitMQ.
 */
router.post('/api/v1/recipe-analysis', async (req, res) => {
  const { user_input } = req.body;
  
  if (!user_input) {
    return res.status(400).json({
      success: false,
      error: 'user_input is required'
    });
  }
  
  try {
    // Send request to AI Service
    const response = await aiClient.analyzeRecipe(user_input);
    
    // Check if AI Service returned success
    if (!response.success) {
      console.error('AI Service error:', response.error);
      return res.status(500).json({
        success: false,
        error: `AI Service error: ${response.error}`
      });
    }
    
    return res.json(response);
    
  } catch (error) {
    console.error('Error calling AI Service:', error);
    
    if (error.message.includes('timeout')) {
      return res.status(504).json({
        success: false,
        error: 'AI Service request timeout'
      });
    }
    
    return res.status(500).json({
      success: false,
      error: `Internal server error: ${error.message}`
    });
  }
});

module.exports = router;
```

**Example: Direct Usage**

```javascript
const { AIServiceClient } = require('./services/rabbitmq-client');

async function main() {
  // Create and connect client
  const client = new AIServiceClient({
    host: 'localhost',
    port: 5672,
    username: 'guest',
    password: 'guest'
  });
  
  await client.connect();
  
  try {
    // Send request
    const response = await client.analyzeRecipe('Tôi muốn ăn phở bò');
    
    // Process response
    if (response.success) {
      const result = response.result;
      console.log(`Dish: ${result.dish.name}`);
      console.log(`Cart items: ${result.cart.total_items}`);
      
      // Check conflicts
      const conflicts = result.conflict_warnings || [];
      if (conflicts.length > 0) {
        console.log(`Found ${conflicts.length} conflicts:`);
        conflicts.forEach(conflict => {
          console.log(`  - ${conflict.conflicting_item_1} vs ${conflict.conflicting_item_2}`);
          console.log(`    Message: ${conflict.message}`);
        });
      }
    } else {
      console.error('Error:', response.error);
    }
    
  } finally {
    await client.close();
  }
}

main().catch(console.error);
```

---

## Request/Response Format

### Request Format

**Queue**: `recipe_analysis_request`

**Message Properties**:
```json
{
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "reply_to": "amq.gen.LhQz1t0Dn1vcU8PeVIfZdQ",
  "content_type": "application/json",
  "delivery_mode": 2
}
```

**Message Body**:
```json
{
  "user_input": "Tôi muốn ăn phở bò"
}
```

**Examples**:
```json
// Simple request
{
  "user_input": "Tôi muốn ăn bún bò Huế"
}

// With extra ingredients
{
  "user_input": "Tôi muốn ăn phở bò với trứng cút và nước mắm"
}

// With excluded ingredients (allergy/preference)
{
  "user_input": "Mình dị ứng đậu phộng, gợi ý phở bò KHÔNG có hành lá"
}
```

### Response Format - Success

**Message Properties**:
```json
{
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "content_type": "application/json"
}
```

**Message Body**:
```json
{
  "success": true,
  "result": {
    "status": "success",
    "dish": {
      "name": "Phở bò",
      "prep_time": "45 phút",
      "servings": "4 người"
    },
    "cart": {
      "total_items": 12,
      "items": [
        {
          "ingredient_id": "ingre05872",
          "name_vi": "Sườn bò",
          "quantity": 1.0,
          "unit": "kg",
          "converted_quantity": "1000",
          "converted_unit": "g",
          "category": "fresh_meat"
        },
        {
          "ingredient_id": "ingre02341",
          "name_vi": "Bánh phở",
          "quantity": 500,
          "unit": "gram",
          "converted_quantity": "500",
          "converted_unit": "g",
          "category": "grains"
        }
      ]
    },
    "conflict_warnings": [
      {
        "conflicting_item_1": ["Bò"],
        "conflicting_item_2": ["Phô mai"],
        "message": "Không nên kết hợp bò với phô mai vì có thể gây khó tiêu",
        "sources": [
          {
            "name": "Dinh dưỡng học cơ bản",
            "url": "https://example.com/nutrition-basics"
          }
        ]
      }
    ],
    "suggestions": [
      {
        "ingredient_id": "ingre05232",
        "name_vi": "Rau cải ngọt",
        "score": 0.95,
        "reason": "Phù hợp với món & chưa có trong giỏ"
      }
    ],
    "similar_dishes": [
      {
        "dish_id": "dish3327",
        "dish_name": "Phở sườn bò",
        "match_ratio": 0.69
      }
    ],
    "warnings": [],
    "insights": [],
    "assistant_response": "",
    "guardrail": {
      "triggered": false,
      "action": "allow",
      "violation_count": 0
    }
  }
}
```

### Response Format - Error

```json
{
  "success": false,
  "error": "Processing error: Dish not found in knowledge base"
}
```

**Common Error Messages**:
- `"Validation error: user_input is required"`
- `"Processing error: Dish not found in knowledge base"`
- `"Processing error: Failed to parse LLM response"`
- `"Guardrail blocked: Content violates safety policies"`

---

## Error Handling

### 1. Timeout Errors

```python
# Python
try:
    response = client.analyze_recipe(user_input)
except TimeoutError as e:
    # Handle timeout
    logger.error(f"AI Service timeout: {e}")
    # Return user-friendly message
    return {
        "success": False,
        "error": "AI Service is taking too long. Please try again."
    }
```

```javascript
// Node.js
try {
  const response = await client.analyzeRecipe(userInput);
} catch (error) {
  if (error.message.includes('timeout')) {
    console.error('AI Service timeout:', error);
    return res.status(504).json({
      success: false,
      error: 'AI Service is taking too long. Please try again.'
    });
  }
}
```

### 2. Connection Errors

```python
# Python - Reconnect logic
try:
    response = client.analyze_recipe(user_input)
except pika.exceptions.AMQPConnectionError:
    logger.error("Lost connection to RabbitMQ. Reconnecting...")
    client._connect()  # Reconnect
    response = client.analyze_recipe(user_input)  # Retry
```

```javascript
// Node.js - Reconnect logic
try {
  const response = await client.analyzeRecipe(userInput);
} catch (error) {
  if (error.message.includes('connection')) {
    console.error('Lost connection to RabbitMQ. Reconnecting...');
    await client.connect();  // Reconnect
    const response = await client.analyzeRecipe(userInput);  // Retry
  }
}
```

### 3. AI Service Errors

```python
# Python - Handle AI Service errors
response = client.analyze_recipe(user_input)

if not response.get('success'):
    error_message = response.get('error', 'Unknown error')
    logger.error(f"AI Service error: {error_message}")
    
    # Return appropriate HTTP status
    if 'Validation error' in error_message:
        raise HTTPException(status_code=400, detail=error_message)
    elif 'Guardrail blocked' in error_message:
        raise HTTPException(status_code=403, detail=error_message)
    else:
        raise HTTPException(status_code=500, detail=error_message)
```

---

## Testing

### 1. Unit Test (Python)

**File: `tests/test_rabbitmq_client.py`**

```python
import pytest
from services.rabbitmq_client import AIServiceClient


@pytest.fixture
def client():
    """Create AI Service client for testing."""
    client = AIServiceClient(
        host='localhost',
        port=5672,
        username='guest',
        password='guest',
        timeout=30
    )
    yield client
    client.close()


def test_basic_recipe_request(client):
    """Test basic recipe analysis request."""
    response = client.analyze_recipe("Tôi muốn ăn phở bò")
    
    assert response['success'] is True
    assert 'result' in response
    
    result = response['result']
    assert 'dish' in result
    assert 'cart' in result
    assert result['dish']['name'] is not None


def test_conflict_detection(client):
    """Test conflict detection in recipe."""
    response = client.analyze_recipe("Tôi muốn ăn bò với phô mai")
    
    assert response['success'] is True
    result = response['result']
    
    conflicts = result.get('conflict_warnings', [])
    if conflicts:
        conflict = conflicts[0]
        assert 'conflicting_item_1' in conflict
        assert 'conflicting_item_2' in conflict
        assert 'message' in conflict
        assert 'sources' in conflict


def test_invalid_request(client):
    """Test empty request handling."""
    response = client.analyze_recipe("")
    
    # AI Service should return error for empty input
    assert response['success'] is False
    assert 'error' in response


def test_timeout():
    """Test timeout handling."""
    client = AIServiceClient(timeout=1)  # 1 second timeout
    
    with pytest.raises(TimeoutError):
        # This should timeout if AI Service is slow
        client.analyze_recipe("Test timeout")
    
    client.close()
```

### 2. Integration Test (Node.js)

**File: `tests/rabbitmq-client.test.js`**

```javascript
const { AIServiceClient } = require('../services/rabbitmq-client');

describe('AIServiceClient', () => {
  let client;

  beforeAll(async () => {
    client = new AIServiceClient({
      host: 'localhost',
      port: 5672,
      username: 'guest',
      password: 'guest',
      timeout: 30000
    });
    await client.connect();
  });

  afterAll(async () => {
    await client.close();
  });

  test('should analyze basic recipe request', async () => {
    const response = await client.analyzeRecipe('Tôi muốn ăn phở bò');
    
    expect(response.success).toBe(true);
    expect(response.result).toBeDefined();
    expect(response.result.dish).toBeDefined();
    expect(response.result.cart).toBeDefined();
    expect(response.result.dish.name).toBeTruthy();
  });

  test('should detect conflicts in recipe', async () => {
    const response = await client.analyzeRecipe('Tôi muốn ăn bò với phô mai');
    
    expect(response.success).toBe(true);
    
    const conflicts = response.result.conflict_warnings || [];
    if (conflicts.length > 0) {
      const conflict = conflicts[0];
      expect(conflict.conflicting_item_1).toBeDefined();
      expect(conflict.conflicting_item_2).toBeDefined();
      expect(conflict.message).toBeDefined();
      expect(conflict.sources).toBeDefined();
    }
  });

  test('should handle empty request', async () => {
    const response = await client.analyzeRecipe('');
    
    // AI Service should return error for empty input
    expect(response.success).toBe(false);
    expect(response.error).toBeDefined();
  });

  test('should timeout on slow requests', async () => {
    const fastClient = new AIServiceClient({ timeout: 1000 }); // 1 second
    await fastClient.connect();
    
    await expect(
      fastClient.analyzeRecipe('Test timeout')
    ).rejects.toThrow('timeout');
    
    await fastClient.close();
  }, 10000);
});
```

### 3. Manual Testing with curl (RabbitMQ Management API)

```bash
# Check queue status
curl -u guest:guest http://localhost:15672/api/queues/%2F/recipe_analysis_request

# Expected output:
# {
#   "name": "recipe_analysis_request",
#   "messages": 0,
#   "consumers": 1,
#   "state": "running"
# }
```

---

## Production Best Practices

### 1. Connection Pooling

**Python - Reuse connections**:
```python
# Use singleton pattern (already implemented in get_ai_service_client())
client = get_ai_service_client()  # Reuses same connection
```

**Node.js - Reuse connections**:
```javascript
// Use singleton pattern (already implemented in getAIServiceClient())
const client = getAIServiceClient();  // Reuses same connection
```

### 2. Health Checks

**Endpoint to check AI Service availability**:

```python
# Python
@router.get("/health/ai-service")
async def health_check_ai_service():
    """Check if AI Service is responsive."""
    try:
        client = get_ai_service_client()
        
        # Send simple test request with timeout
        response = client.analyze_recipe("test", timeout=5)
        
        return {
            "status": "healthy",
            "ai_service": "connected"
        }
    except TimeoutError:
        return {
            "status": "degraded",
            "ai_service": "slow_response"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "ai_service": "disconnected",
            "error": str(e)
        }
```

### 3. Retry Logic

```python
# Python - Exponential backoff retry
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def analyze_recipe_with_retry(user_input: str):
    """Analyze recipe with automatic retry."""
    client = get_ai_service_client()
    return client.analyze_recipe(user_input)
```

### 4. Monitoring and Logging

```python
# Python - Structured logging
import logging
import time

logger = logging.getLogger(__name__)

def analyze_recipe_monitored(user_input: str):
    """Analyze recipe with monitoring."""
    start_time = time.time()
    
    try:
        client = get_ai_service_client()
        response = client.analyze_recipe(user_input)
        
        # Log success metrics
        duration = time.time() - start_time
        logger.info(
            "AI Service request successful",
            extra={
                "duration_ms": duration * 1000,
                "success": response.get('success'),
                "user_input_length": len(user_input)
            }
        )
        
        return response
        
    except Exception as e:
        # Log error metrics
        duration = time.time() - start_time
        logger.error(
            "AI Service request failed",
            extra={
                "duration_ms": duration * 1000,
                "error": str(e),
                "user_input_length": len(user_input)
            }
        )
        raise
```

### 5. Rate Limiting

```python
# Python - Rate limiting with Redis
from redis import Redis
from datetime import timedelta

redis_client = Redis(host='localhost', port=6379)

def check_rate_limit(user_id: str) -> bool:
    """
    Check if user has exceeded rate limit.
    Limit: 10 requests per minute
    """
    key = f"rate_limit:ai_service:{user_id}"
    count = redis_client.incr(key)
    
    if count == 1:
        redis_client.expire(key, timedelta(minutes=1))
    
    return count <= 10  # Max 10 requests per minute
```

### 6. Circuit Breaker

```python
# Python - Circuit breaker pattern
from pybreaker import CircuitBreaker

# Circuit breaker: open after 5 failures, timeout 60s
ai_service_breaker = CircuitBreaker(
    fail_max=5,
    timeout_duration=60,
    name='ai_service'
)

@ai_service_breaker
def analyze_recipe_with_breaker(user_input: str):
    """Analyze recipe with circuit breaker."""
    client = get_ai_service_client()
    return client.analyze_recipe(user_input)
```

---

## Troubleshooting

### Issue: Connection Refused

**Symptoms**:
```
pika.exceptions.AMQPConnectionError: Connection refused
```

**Solutions**:
1. Check if RabbitMQ is running:
   ```bash
   # Docker
   docker ps | grep rabbitmq
   
   # Linux service
   sudo systemctl status rabbitmq-server
   
   # Windows
   rabbitmq-service status
   ```

2. Check if port 5672 is open:
   ```bash
   telnet localhost 5672
   ```

3. Verify connection parameters in `.env`

### Issue: Authentication Failed

**Symptoms**:
```
pika.exceptions.ProbableAuthenticationError
```

**Solutions**:
1. Check credentials in `.env`:
   ```bash
   RABBITMQ_USERNAME=guest
   RABBITMQ_PASSWORD=guest
   ```

2. Verify user exists in RabbitMQ:
   ```bash
   rabbitmqctl list_users
   ```

3. Create user if needed:
   ```bash
   rabbitmqctl add_user myuser mypassword
   rabbitmqctl set_permissions -p / myuser ".*" ".*" ".*"
   ```

### Issue: Timeout on Every Request

**Symptoms**:
```
TimeoutError: No response from AI Service within 30 seconds
```

**Solutions**:
1. Check if AI Service worker is running:
   ```bash
   # Look for process
   ps aux | grep run_rabbitmq_worker
   ```

2. Check AI Service logs:
   ```bash
   tail -f rabbitmq_worker.log
   ```

3. Verify queue has consumer:
   - Go to http://localhost:15672
   - Check queue `recipe_analysis_request`
   - Should have 1 consumer

4. Increase timeout if AI Service is slow:
   ```bash
   AI_SERVICE_TIMEOUT=60000  # 60 seconds
   ```

### Issue: Messages Not Being Consumed

**Symptoms**:
- Messages accumulate in `recipe_analysis_request` queue
- No responses received

**Solutions**:
1. Check AI Service worker is consuming:
   ```bash
   # RabbitMQ Management UI
   # Queue -> recipe_analysis_request -> Consumers should be 1
   ```

2. Restart AI Service worker:
   ```bash
   # Stop existing worker
   pkill -f run_rabbitmq_worker
   
   # Start new worker
   python run_rabbitmq_worker.py
   ```

3. Check for errors in AI Service logs

### Issue: Duplicate Responses

**Symptoms**:
- Receiving multiple responses for same request

**Solutions**:
1. Ensure only one AI Service worker instance is running:
   ```bash
   ps aux | grep run_rabbitmq_worker | grep -v grep
   ```

2. Use singleton pattern for client (already implemented)

3. Check correlation_id matching is working correctly

### Issue: Memory Leak

**Symptoms**:
- Memory usage increases over time
- Application becomes slow

**Solutions**:
1. Close connections properly:
   ```python
   # Always use context manager
   with AIServiceClient() as client:
       response = client.analyze_recipe(user_input)
   ```

2. Clear response handlers after timeout (Node.js):
   ```javascript
   // Already implemented in timeout handler
   this.responseHandlers.delete(correlationId);
   ```

3. Monitor connection pool size

---

## Performance Metrics

### Expected Latency

| Operation | Expected Time |
|-----------|--------------|
| Simple recipe (phở bò) | 3-5 seconds |
| Complex recipe with conflicts | 5-8 seconds |
| Recipe with RAG search | 4-7 seconds |
| Network roundtrip (RabbitMQ) | 50-100ms |

### Throughput

- **Single AI Service worker**: ~10-15 requests/minute
- **Multiple workers (3)**: ~30-40 requests/minute
- **Recommended**: Scale AI Service workers horizontally for higher throughput

### Resource Usage

**Main Service**:
- Memory: ~50MB per connection
- CPU: <5% during requests

**RabbitMQ**:
- Memory: ~100-200MB (idle)
- CPU: <10% with moderate load

---

## Appendix

### A. Environment Variables Reference

```bash
# RabbitMQ Configuration
RABBITMQ_HOST=localhost           # RabbitMQ host
RABBITMQ_PORT=5672                # RabbitMQ port
RABBITMQ_USERNAME=guest           # RabbitMQ username
RABBITMQ_PASSWORD=guest           # RabbitMQ password
RABBITMQ_VIRTUAL_HOST=/           # Virtual host

# AI Service Configuration
AI_SERVICE_QUEUE=recipe_analysis_request  # Queue name
AI_SERVICE_TIMEOUT=30000                  # Timeout in milliseconds

# Monitoring
LOG_LEVEL=INFO                    # Logging level
ENABLE_METRICS=true               # Enable Prometheus metrics
```

### B. RabbitMQ Management Commands

```bash
# List queues
rabbitmqctl list_queues name messages consumers

# Purge queue (clear all messages)
rabbitmqctl purge_queue recipe_analysis_request

# Delete queue
rabbitmqctl delete_queue recipe_analysis_request

# List connections
rabbitmqctl list_connections

# Close connection
rabbitmqctl close_connection "<connection_name>" "Maintenance"
```

### C. Docker Compose Setup

**File: `docker-compose.yml`**

```yaml
version: '3.8'

services:
  rabbitmq:
    image: rabbitmq:3-management
    container_name: rabbitmq
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      RABBITMQ_DEFAULT_USER: admin
      RABBITMQ_DEFAULT_PASS: admin123
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    healthcheck:
      test: rabbitmq-diagnostics -q ping
      interval: 30s
      timeout: 10s
      retries: 5
    networks:
      - app_network

  main-service:
    build: .
    container_name: main-service
    depends_on:
      rabbitmq:
        condition: service_healthy
    environment:
      RABBITMQ_HOST: rabbitmq
      RABBITMQ_PORT: 5672
      RABBITMQ_USERNAME: admin
      RABBITMQ_PASSWORD: admin123
    ports:
      - "8000:8000"
    networks:
      - app_network

volumes:
  rabbitmq_data:

networks:
  app_network:
    driver: bridge
```

**Run with Docker Compose**:
```bash
docker-compose up -d
```

---

## Support and Resources

### Documentation
- **AI Service RabbitMQ Guide**: See `RABBITMQ_GUIDE.md` in AI_Service repository
- **AI Service README**: See `README.md` in AI_Service repository
- **RabbitMQ Official Docs**: https://www.rabbitmq.com/documentation.html

### Architecture Diagram
- See section [Architecture](#architecture) above

### Contact
- **Repository**: https://github.com/PTIT-KLTN/AI_Service
- **Issues**: https://github.com/PTIT-KLTN/AI_Service/issues

---

**Document End**

*Last updated: October 30, 2025*  
*Version: 1.0*
